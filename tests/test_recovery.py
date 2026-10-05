"""Regression tests for QQ outages with a still-open OneBot WebSocket."""
import asyncio
from dataclasses import replace
import json
import time
import unittest
from unittest.mock import patch

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from config import Config
from onebot import APIError, OneBotClient, SessionReset, run
from poke import PokeHandler
from tests.test_poke import event


async def reply(ws, request, data):
    await ws.send(json.dumps(dict(status='ok', retcode=0, echo=request['echo'], data=data)))


async def stop(task):
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_poll_recovers_qq_without_server_closing_websocket(self):
        connections = 0
        online = False
        offline_seen = asyncio.Event()
        finished = asyncio.Event()
        pokes = []

        async def server(ws):
            nonlocal connections
            connections += 1
            number = connections
            async for raw in ws:
                request = json.loads(raw)
                if request['action'] == 'get_login_info':
                    await reply(ws, request, {'user_id': 123456})
                elif request['action'] == 'get_status':
                    await reply(ws, request, {'online': online, 'good': True})
                    if not online:
                        # These fresh notices must be discarded while offline.
                        await ws.send(json.dumps(event(time=int(time.time()), user_id=444444)))
                        offline_seen.set()
                    elif number >= 2:
                        await ws.send(json.dumps(event(time=int(time.time()), user_id=555555)))
                elif request['action'] == 'group_poke':
                    pokes.append(request['params'])
                    await reply(ws, request, None)
                    finished.set()

        async with serve(server, '127.0.0.1', 0) as service:
            cfg = replace(Config(), ws_url=f'ws://127.0.0.1:{service.sockets[0].getsockname()[1]}',
                          healthcheck_seconds=.02, reconnect_seconds=.01)
            task = asyncio.create_task(run(cfg, PokeHandler(cfg)))
            try:
                await asyncio.wait_for(offline_seen.wait(), 3)
                await asyncio.sleep(.04)
                self.assertEqual(pokes, [])
                online = True
                await asyncio.wait_for(finished.wait(), 3)
                self.assertGreaterEqual(connections, 2)
                self.assertEqual(pokes, [{'group_id': '654321', 'user_id': '555555'}])
            finally:
                await stop(task)

    async def test_heartbeat_recovery_reconnects_and_preserves_dedup(self):
        connections = 0
        finished = asyncio.Event()
        pokes = []
        first_event = event(time=int(time.time()))

        async def server(ws):
            nonlocal connections
            connections += 1
            number = connections
            async for raw in ws:
                request = json.loads(raw)
                if request['action'] == 'get_login_info':
                    await reply(ws, request, {'user_id': 123456})
                elif request['action'] == 'get_status':
                    await reply(ws, request, {'online': True, 'good': True})
                    await ws.send(json.dumps(first_event))
                    if number >= 2:
                        await ws.send(json.dumps(event(time=int(time.time()), user_id=555555)))
                elif request['action'] == 'group_poke':
                    pokes.append(request['params'])
                    await reply(ws, request, None)
                    if number == 1:
                        for _ in range(3):
                            await ws.send(json.dumps(dict(meta_event_type='heartbeat', status={'online': False})))
                        await ws.send(json.dumps(event(time=int(time.time()), user_id=444444)))
                        await ws.send(json.dumps(dict(meta_event_type='heartbeat', status={'online': True})))
                    else:
                        finished.set()

        async with serve(server, '127.0.0.1', 0) as service:
            cfg = replace(Config(), ws_url=f'ws://127.0.0.1:{service.sockets[0].getsockname()[1]}',
                          reconnect_seconds=.01, global_interval_seconds=.001)
            with patch('onebot.log.warning') as warning:
                task = asyncio.create_task(run(cfg, PokeHandler(cfg)))
                try:
                    await asyncio.wait_for(finished.wait(), 3)
                    self.assertEqual([item['user_id'] for item in pokes], ['987654', '555555'])
                    self.assertEqual(connections, 2)
                    # Repeated offline heartbeats must not flood the log.
                    self.assertEqual(warning.call_count, 1)
                finally:
                    await stop(task)

    async def test_api_hang_reconnects_even_if_websocket_ping_still_works(self):
        connections = 0
        status_calls = 0
        recovered = asyncio.Event()
        pokes = []

        async def server(ws):
            nonlocal connections, status_calls
            connections += 1
            number = connections
            async for raw in ws:
                request = json.loads(raw)
                if request['action'] == 'get_login_info':
                    await reply(ws, request, {'user_id': 123456})
                elif request['action'] == 'get_status':
                    status_calls += 1
                    if number == 1 and status_calls > 1:
                        # TCP and ping/pong remain alive; the application API hangs.
                        continue
                    await reply(ws, request, {'online': True})
                    if number >= 2:
                        recovered.set()
                elif request['action'] == 'group_poke':
                    pokes.append(request)

        async with serve(server, '127.0.0.1', 0) as service:
            cfg = replace(Config(), ws_url=f'ws://127.0.0.1:{service.sockets[0].getsockname()[1]}',
                          healthcheck_seconds=.02, api_timeout_seconds=.08, reconnect_seconds=.01)
            task = asyncio.create_task(run(cfg, PokeHandler(cfg)))
            try:
                await asyncio.wait_for(recovered.wait(), 3)
                self.assertGreaterEqual(connections, 2)
                self.assertEqual(pokes, [])
            finally:
                await stop(task)

    async def test_persistent_offline_refreshes_connection_without_sending(self):
        connections = 0
        refreshed = asyncio.Event()
        pokes = []

        async def server(ws):
            nonlocal connections
            connections += 1
            number = connections
            async for raw in ws:
                request = json.loads(raw)
                if request['action'] == 'get_login_info':
                    await reply(ws, request, {'user_id': 123456})
                elif request['action'] == 'get_status':
                    await reply(ws, request, {'online': False})
                    await ws.send(json.dumps(event(time=int(time.time()))))
                    if number >= 2:
                        refreshed.set()
                elif request['action'] == 'group_poke':
                    pokes.append(request)

        async with serve(server, '127.0.0.1', 0) as service:
            cfg = replace(Config(), ws_url=f'ws://127.0.0.1:{service.sockets[0].getsockname()[1]}',
                          healthcheck_seconds=.02, offline_reconnect_seconds=.03, reconnect_seconds=.01)
            task = asyncio.create_task(run(cfg, PokeHandler(cfg)))
            try:
                await asyncio.wait_for(refreshed.wait(), 3)
                self.assertGreaterEqual(connections, 2)
                self.assertEqual(pokes, [])
            finally:
                await stop(task)

    def test_invalid_status_fails_closed_and_old_session_stays_paused(self):
        client = OneBotClient(None, Config())
        with self.assertRaises(APIError):
            client.update_status({'good': True})
        client.events.put_nowait((time.monotonic(), event()))
        client.update_status({'online': False})
        self.assertTrue(client.events.empty())
        with self.assertRaises(SessionReset):
            client.update_status({'online': True})
        self.assertIs(client.online, False)
