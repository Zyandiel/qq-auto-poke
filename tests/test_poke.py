import unittest
from unittest.mock import AsyncMock

from config import Config
from poke import PokeHandler


def event(**changes):
    result = dict(post_type="notice", notice_type="notify", sub_type="poke",
                  self_id=123456, group_id=654321, user_id=987654,
                  target_id=123456, time=1000)
    result.update(changes)
    return result


class PokeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = 1000
        self.handler = PokeHandler(Config(), clock=lambda: self.now, wall_clock=lambda: self.now)
        self.send = AsyncMock()

    async def handle(self, value):
        return await self.handler.handle_poke_event(value, 123456, self.send)

    async def test_valid_and_string_ids(self):
        self.assertTrue(await self.handle(event(user_id="987654", target_id="123456")))
        self.send.assert_awaited_once_with(654321, 987654)

    async def test_unrelated_and_malformed_events(self):
        for value in [None, [], event(group_id=None), event(user_id=123456),
                      event(target_id=111111), event(self_id=111111), event(user_id=True),
                      event(user_id=12.5), event(user_id={}), event(group_id=0),
                      event(post_type="message"), event(notice_type="group_recall"),
                      event(sub_type="honor"), event(time=None), event(time=999999),
                      event(time=900), event(time=float("nan")), event(time=float("inf")),
                      event(time=10**400), event(user_id="9"*5000), event(user_id=10**5000)]:
            with self.subTest(value=value):
                self.assertFalse(await self.handle(value))
        self.send.assert_not_awaited()

    async def test_own_echo_does_not_loop(self):
        await self.handle(event())
        self.now += 4
        self.assertFalse(await self.handle(event(user_id=123456, target_id=987654, time=self.now)))
        self.send.assert_awaited_once()

    async def test_cooldown_and_dedup(self):
        original = event()
        await self.handle(original)
        self.now += 2
        self.assertFalse(await self.handle(event(time=self.now)))
        self.now += 2
        self.assertFalse(await self.handle(original))
        self.assertTrue(await self.handle(event(time=self.now)))
        self.assertEqual(self.send.await_count, 2)

    async def test_global_rate_limit(self):
        await self.handle(event())
        self.assertFalse(await self.handle(event(user_id=888888, group_id=777777)))
        self.now += 1
        self.assertTrue(await self.handle(event(user_id=888888, group_id=777777, time=self.now)))

    async def test_failed_send_is_not_retried(self):
        self.send.side_effect = RuntimeError("packetBackend unavailable")
        with self.assertLogs("auto_poke", level="ERROR") as captured:
            self.assertFalse(await self.handle(event()))
        self.assertIn("packetBackend", captured.output[0])
        self.now += 4
        self.assertFalse(await self.handle(event()))
        self.send.assert_awaited_once()
