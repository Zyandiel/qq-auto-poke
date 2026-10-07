"""Use fresh OneBot metadata, rather than a poke, to align event clocks."""
import asyncio
from dataclasses import replace
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from websockets.asyncio.server import serve

from config import Config
from onebot import OneBotClient, run
from poke import PokeHandler


SELF = 101
GROUP = 202
SENDER = 303


def notice(stamp, **changes):
    result = dict(post_type="notice", notice_type="notify", sub_type="poke",
                  self_id=SELF, group_id=GROUP, user_id=SENDER,
                  target_id=SELF, time=stamp)
    result.update(changes)
    return result


def metadata(stamp, **changes):
    result = dict(post_type="meta_event", meta_event_type="lifecycle",
                  sub_type="connect", self_id=SELF, time=stamp)
    result.update(changes)
    return result


async def stop(task):
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


class EventClockTests(unittest.IsolatedAsyncioTestCase):
    async def exercise_server(self, offset, *, include_old_and_future=False):
        requests = []
        finished = asyncio.Event()

        async def server(ws):
            # NapCat emits this when a new event-capable connection opens,
            # before get_login_info has verified the account at the client.
            stamp = int(time.time()) + offset
            await ws.send(json.dumps(metadata(stamp)))
            async for raw in ws:
                request = json.loads(raw)
                action = request["action"]
                if action == "get_login_info":
                    data = {"user_id": SELF}
                elif action == "get_status":
                    data = {"online": True, "good": True}
                elif action == "group_poke":
                    requests.append(request["params"])
                    data = None
                else:
                    raise AssertionError(f"Unexpected action: {action}")
                await ws.send(json.dumps(dict(status="ok", retcode=0,
                                             echo=request["echo"], data=data)))
                if action == "get_status":
                    if include_old_and_future:
                        await ws.send(json.dumps(notice(stamp - 31, user_id=404)))
                        await ws.send(json.dumps(notice(stamp + 60, user_id=505)))
                    await ws.send(json.dumps(notice(stamp)))
                elif action == "group_poke" and request["params"]["user_id"] == str(SENDER):
                    finished.set()

        async with serve(server, "127.0.0.1", 0) as service:
            port = service.sockets[0].getsockname()[1]
            cfg = replace(Config(), ws_url=f"ws://127.0.0.1:{port}",
                          reconnect_seconds=.01, global_interval_seconds=.00001)
            task = asyncio.create_task(run(cfg, PokeHandler(cfg)))
            try:
                await asyncio.wait_for(finished.wait(), 3)
                self.assertEqual(requests, [{"group_id": str(GROUP), "user_id": str(SENDER)}])
            finally:
                await stop(task)

    async def test_real_websocket_accepts_fresh_pokes_with_both_clock_offsets(self):
        for offset in (-38488, 38488):
            with self.subTest(offset=offset):
                await self.exercise_server(offset)

    async def test_real_websocket_still_rejects_old_and_future_pokes(self):
        for offset in (-38488, 38488):
            with self.subTest(offset=offset):
                await self.exercise_server(offset, include_old_and_future=True)

    async def test_recovery_rebuilds_clock_and_rejects_an_old_session_replay(self):
        connections = 0
        requests = []
        original = None
        finished = asyncio.Event()
        recovered_sender = 606

        async def server(ws):
            nonlocal connections, original
            connections += 1
            number = connections
            offset = -38488 if number == 1 else 38488
            stamp = int(time.time()) + offset
            await ws.send(json.dumps(metadata(stamp)))
            async for raw in ws:
                request = json.loads(raw)
                action = request["action"]
                if action == "get_login_info":
                    data = {"user_id": SELF}
                elif action == "get_status":
                    data = {"online": True, "good": True}
                elif action == "group_poke":
                    requests.append(request["params"])
                    data = None
                else:
                    raise AssertionError(f"Unexpected action: {action}")
                await ws.send(json.dumps(dict(status="ok", retcode=0,
                                             echo=request["echo"], data=data)))
                if action == "get_status":
                    if number == 1:
                        original = notice(stamp)
                        await ws.send(json.dumps(original))
                    else:
                        # The old timestamp must not become fresh just because
                        # this is a new WebSocket with a new clock reference.
                        await ws.send(json.dumps(original))
                        await ws.send(json.dumps(notice(stamp, user_id=recovered_sender)))
                elif action == "group_poke":
                    if number == 1:
                        await ws.send(json.dumps(metadata(
                            int(time.time()) - 38488, meta_event_type="heartbeat",
                            status={"online": False, "good": True})))
                        await ws.send(json.dumps(metadata(
                            int(time.time()) + 38488, meta_event_type="heartbeat",
                            status={"online": True, "good": True})))
                    elif request["params"]["user_id"] == str(recovered_sender):
                        finished.set()

        async with serve(server, "127.0.0.1", 0) as service:
            port = service.sockets[0].getsockname()[1]
            cfg = replace(Config(), ws_url=f"ws://127.0.0.1:{port}",
                          reconnect_seconds=.01, global_interval_seconds=.00001)
            task = asyncio.create_task(run(cfg, PokeHandler(cfg)))
            try:
                await asyncio.wait_for(finished.wait(), 3)
                self.assertGreaterEqual(connections, 2)
                self.assertEqual(requests, [
                    {"group_id": str(GROUP), "user_id": str(SENDER)},
                    {"group_id": str(GROUP), "user_id": str(recovered_sender)},
                ])
            finally:
                await stop(task)

    def test_only_valid_matching_metadata_can_establish_a_clock(self):
        invalid = [
            notice(1000),
            metadata(1000, post_type="message"),
            metadata(1000, meta_event_type="lifecycle", sub_type="enable"),
            metadata(1000, meta_event_type="unknown"),
            metadata(1000, self_id=999),
            metadata(1000, self_id=None),
            metadata(1000, self_id=True),
            metadata(None), metadata(True), metadata("1000"),
            metadata(float("nan")), metadata(float("inf")), metadata(10**400),
        ]
        for sample in invalid:
            with self.subTest(sample=sample):
                client = OneBotClient(None, Config())
                client.self_id = SELF
                client.observe_clock(sample)
                self.assertIsNone(client.clock_reference)
                self.assertIsNone(client.event_time(client.clock_reference))
        for sample in [metadata(1000), metadata(1000, meta_event_type="heartbeat",
                                              status={"online": True, "good": True})]:
            with self.subTest(valid=sample):
                client = OneBotClient(None, Config())
                client.self_id = SELF
                with patch("onebot.time.monotonic", return_value=10):
                    client.observe_clock(sample)
                    self.assertEqual(client.event_time(client.clock_reference), 1001)

    def test_login_candidate_is_used_only_after_matching_identity_is_verified(self):
        client = OneBotClient(None, Config())
        with patch("onebot.time.monotonic", return_value=10):
            client.observe_clock(metadata(1000))
            reference = client.clock_reference
            self.assertIsNotNone(reference)
            self.assertIsNone(client.event_time(reference))
            client.self_id = 999
            self.assertIsNone(client.event_time(reference))
            client.self_id = SELF
            self.assertEqual(client.event_time(reference), 1001)
        self.assertIsNone(client.event_time(None))

    async def test_second_precision_upper_bound_accepts_a_normal_second_boundary(self):
        client = OneBotClient(None, Config())
        client.self_id = SELF
        with patch("onebot.time.monotonic", return_value=10):
            client.observe_clock(metadata(1000))
        # The metadata could have been generated at 1000.9 and the poke at
        # 1001.1. A raw anchor estimate of 1000.2 would incorrectly reject it.
        with patch("onebot.time.monotonic", return_value=10.2):
            event_now = client.event_time(client.clock_reference)
        self.assertAlmostEqual(event_now, 1001.2)
        send = AsyncMock()
        handler = PokeHandler(Config(), clock=lambda: 10.2, wall_clock=lambda: 90000)
        self.assertTrue(await handler.handle_poke_event(notice(1001), SELF, send,
                                                       event_now=event_now))
        send.assert_awaited_once_with(GROUP, SENDER)

    def test_local_wall_clock_jumps_do_not_change_an_established_remote_clock(self):
        client = OneBotClient(None, Config())
        client.self_id = SELF
        with patch("onebot.time.monotonic", return_value=10):
            client.observe_clock(metadata(1000))
        for wall_now in (100000, -100000):
            with self.subTest(wall_now=wall_now):
                with patch("onebot.time.time", return_value=wall_now), \
                        patch("onebot.time.monotonic", return_value=12):
                    self.assertEqual(client.event_time(client.clock_reference), 1003)

    async def test_queued_event_uses_reference_at_receipt_not_a_later_clock_jump(self):
        monotonic = [10.0]

        class Frames:
            async def __aiter__(self):
                frames = [
                    (10, metadata(1000)),
                    (10.5, notice(1001)),
                    (11, metadata(5000, meta_event_type="heartbeat",
                                  status={"online": True, "good": True})),
                ]
                for received, frame in frames:
                    monotonic[0] = received
                    yield json.dumps(frame)

        client = OneBotClient(Frames(), Config())
        client.self_id = SELF
        client.online = True
        # Replace onebot's module reference so asyncio's timeout clock keeps
        # advancing even when this synthetic event clock is held still.
        with patch("onebot.time", SimpleNamespace(monotonic=lambda: monotonic[0], time=time.time)):
            await client.read_messages()
            queued = client.events.get_nowait()
            self.assertEqual(len(queued), 3)
            self.assertNotEqual(queued[2], client.clock_reference)
            client.events.put_nowait(queued)
            monotonic[0] = 12
            self.assertEqual(client.event_time(queued[2]), 1003)
            self.assertEqual(client.event_time(client.clock_reference), 5002)
            sent = asyncio.Event()

            async def send(*_args):
                sent.set()

            client.send_group_poke = AsyncMock(side_effect=send)
            handler = PokeHandler(Config(), clock=lambda: monotonic[0], wall_clock=lambda: 90000)
            worker = asyncio.create_task(client.process_events(handler, SELF))
            try:
                await asyncio.wait_for(sent.wait(), 1)
                client.send_group_poke.assert_awaited_once_with(GROUP, SENDER)
            finally:
                await stop(worker)

    async def test_clock_alignment_preserves_original_timestamp_for_dedup(self):
        now = [10.0]
        cfg = Config(cooldown_seconds=1, global_interval_seconds=.1)
        handler = PokeHandler(cfg, clock=lambda: now[0], wall_clock=lambda: 90000)
        incoming = notice(1000)
        send = AsyncMock()
        self.assertTrue(await handler.handle_poke_event(incoming, SELF, send, event_now=1001))
        now[0] += 4
        self.assertFalse(await handler.handle_poke_event(incoming, SELF, send, event_now=1005))
        self.assertEqual(incoming["time"], 1000)
        self.assertTrue(await handler.handle_poke_event(notice(1005), SELF, send, event_now=1006))
        self.assertEqual(send.await_count, 2)
