import asyncio
from dataclasses import replace
import json
import time
import unittest
from unittest.mock import AsyncMock

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from config import Config
from onebot import APIError, OneBotClient, run
from poke import PokeHandler
from tests.test_poke import event


class WebSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_end_to_end_and_echo_filter(self):
        requests = []
        errors = []

        async def server(ws):
            try:
                self.assertEqual(ws.request.headers['Authorization'], 'Bearer local-test')
                login = json.loads(await ws.recv())
                self.assertEqual(login['action'], 'get_login_info')
                # 事件在登录回包之前到达，不能丢失或阻塞回包读取。
                incoming = event(time=int(time.time()))
                await ws.send(json.dumps(incoming))
                await ws.send(json.dumps(dict(status='ok', retcode=0,
                                             data={'user_id': 123456}, echo=login['echo'])))
                poke = json.loads(await asyncio.wait_for(ws.recv(), 2))
                requests.append(poke)
                await ws.send('not json')
                await ws.send('[]')
                await ws.send(json.dumps(dict(status='ok', retcode=0, echo=poke['echo'], data=None)))
                await ws.send(json.dumps(incoming))
                await ws.send(json.dumps(event(time=int(time.time()), user_id=123456, target_id=987654)))
                try:
                    extra = await asyncio.wait_for(ws.recv(), .15)
                    errors.append(f'unexpected request: {extra}')
                except TimeoutError:
                    pass
            except Exception as exc:
                errors.append(repr(exc))

        async with serve(server, '127.0.0.1', 0) as service:
            port = service.sockets[0].getsockname()[1]
            cfg = Config(access_token='local-test')
            async with connect(f'ws://127.0.0.1:{port}', proxy=None,
                               additional_headers={'Authorization': 'Bearer local-test'}) as ws:
                await asyncio.wait_for(OneBotClient(ws, cfg).session(PokeHandler(cfg)), 3)
        self.assertEqual(errors, [])
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]['action'], 'group_poke')
        self.assertEqual(requests[0]['params'], {'group_id': '654321', 'user_id': '987654'})

    async def test_failed_api_and_timeout_cleanup(self):
        calls = 0
        async def server(ws):
            nonlocal calls
            async for raw in ws:
                calls += 1
                request = json.loads(raw)
                if calls == 1:
                    await ws.send(json.dumps(dict(status='failed', retcode=1404,
                        message='unsupported group_poke', echo=request['echo'])))

        async with serve(server, '127.0.0.1', 0) as service:
            port = service.sockets[0].getsockname()[1]
            async with connect(f'ws://127.0.0.1:{port}', proxy=None) as ws:
                client = OneBotClient(ws, Config(api_timeout_seconds=.1))
                reader = asyncio.create_task(client.read_messages())
                try:
                    with self.assertRaisesRegex(APIError, '1404.*unsupported'):
                        await client.send_group_poke(654321, 987654)
                    with self.assertRaisesRegex(APIError, '超时'):
                        await client.send_group_poke(654321, 987654)
                    self.assertEqual(client.pending, {})
                    self.assertEqual(calls, 2)
                finally:
                    reader.cancel()
                    await asyncio.gather(reader, return_exceptions=True)

    async def test_auth_rejection(self):
        async def server(ws):
            await ws.recv()
            await ws.send(json.dumps(dict(status='failed', retcode=1403, message='token验证失败')))
            await ws.close()
        async with serve(server, '127.0.0.1', 0) as service:
            port = service.sockets[0].getsockname()[1]
            async with connect(f'ws://127.0.0.1:{port}', proxy=None) as ws:
                with self.assertRaisesRegex(APIError, 'token'):
                    await OneBotClient(ws, Config()).session(PokeHandler(Config()))

    async def test_identity_mismatch(self):
        client = OneBotClient(None, Config(self_id=999999))
        client.call = AsyncMock(return_value={'user_id': 123456})
        client.read_messages = AsyncMock()
        with self.assertRaisesRegex(APIError, '不一致'):
            await client.session(PokeHandler(Config()))

    async def test_disconnect_cleans_pending_call_without_retry(self):
        requests = []

        async def server(ws):
            requests.append(json.loads(await ws.recv()))
            await ws.close()

        async with serve(server, '127.0.0.1', 0) as service:
            port = service.sockets[0].getsockname()[1]
            async with connect(f'ws://127.0.0.1:{port}', proxy=None) as ws:
                client = OneBotClient(ws, Config())
                reader = asyncio.create_task(client.read_messages())
                try:
                    with self.assertRaisesRegex(APIError, '断开.*不自动重试'):
                        await client.send_group_poke(654321, 987654)
                    self.assertEqual(client.pending, {})
                    self.assertEqual(len(requests), 1)
                finally:
                    reader.cancel()
                    await asyncio.gather(reader, return_exceptions=True)

    async def test_reconnect_preserves_dedup(self):
        connections = 0
        pokes = []
        ready = asyncio.Event()
        incoming = event(time=int(time.time()))
        async def server(ws):
            nonlocal connections
            connections += 1
            login = json.loads(await ws.recv())
            await ws.send(json.dumps(dict(status='ok', retcode=0, echo=login['echo'], data={'user_id': 123456})))
            await ws.send(json.dumps(incoming))
            if connections == 1:
                poke = json.loads(await ws.recv())
                pokes.append(poke)
                await ws.send(json.dumps(dict(status='ok', retcode=0, echo=poke['echo'])))
                await asyncio.sleep(.03)
            else:
                try:
                    pokes.append(await asyncio.wait_for(ws.recv(), .1))
                except TimeoutError:
                    ready.set()
                await ws.wait_closed()

        async with serve(server, '127.0.0.1', 0) as service:
            port = service.sockets[0].getsockname()[1]
            cfg = replace(Config(), ws_url=f'ws://127.0.0.1:{port}', reconnect_seconds=.02)
            task = asyncio.create_task(run(cfg, PokeHandler(cfg)))
            try:
                await asyncio.wait_for(ready.wait(), 3)
                self.assertEqual(len(pokes), 1)
                self.assertGreaterEqual(connections, 2)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
