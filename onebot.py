"""OneBot 11 通信：单独读取回包，避免处理事件时等待 API 导致死锁。"""
import asyncio
import json
import logging
import time
import uuid

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from config import qq_id
from poke import is_group_poke

log = logging.getLogger("auto_poke")


class APIError(RuntimeError):
    pass


class SessionReset(APIError):
    """需要刷新监听会话的状态变化，不表示发送成功或重新登录 QQ。"""


class OneBotClient:
    def __init__(self, websocket, config):
        self.ws = websocket
        self.config = config
        self.pending = {}
        self.events = asyncio.Queue(maxsize=100)
        self.online = None
        self.offline_since = None

    def update_status(self, status):
        if not isinstance(status, dict) or not isinstance(status.get("online"), bool):
            raise APIError("get_status 未返回有效 online 状态，拒绝反戳")
        online = status["online"] and status.get("good") is not False
        previous = self.online
        if online and previous is False:
            # 旧会话保持暂停，直到新连接重新核对账号与在线状态。
            raise SessionReset("QQ 已恢复在线，正在重新建立监听会话")
        self.online = online
        if not online:
            # 离线期间的通知即便 time 仍新鲜也不能在恢复后补发。
            while not self.events.empty():
                self.events.get_nowait()
            if previous is not False:
                self.offline_since = time.monotonic()
                log.warning("QQ 离线或 NapCat 状态异常，已暂停反戳，等待恢复")

    async def check_status(self):
        self.update_status(await self.call("get_status"))

    async def monitor_connection(self):
        while True:
            await asyncio.sleep(self.config.healthcheck_seconds)
            await self.check_status()
            if (self.online is False and self.offline_since is not None
                    and time.monotonic() - self.offline_since >= self.config.offline_reconnect_seconds):
                raise SessionReset("QQ 持续离线，正在刷新 OneBot 连接；若 QQ 能聊天仍无事件，请重新启动 NapCat")

    async def call(self, action, params=None):
        echo = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.pending[echo] = future
        try:
            async with asyncio.timeout(self.config.api_timeout_seconds):
                await self.ws.send(json.dumps({"action": action, "params": params or {}, "echo": echo}))
                response = await future
            if response.get("status") != "ok" or response.get("retcode") != 0:
                reason = response.get("message") or response.get("wording") or "未知错误"
                raise APIError(f"{action}: retcode={response.get('retcode')}, {reason}")
            return response.get("data")
        except TimeoutError as exc:
            reason = f"{action} 超时"
            if action == "group_poke":
                reason += "，执行结果未知，不自动重试"
            raise APIError(reason) from exc
        finally:
            self.pending.pop(echo, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                # send 失败与 reader 断线可能同时发生，清理尚未 await 的异常。
                future.exception()

    async def send_group_poke(self, group_id, user_id):
        # NapCat 扩展 action 是 group_poke；字符串参数符合其 schema。
        await self.call("group_poke", {"group_id": str(group_id), "user_id": str(user_id)})

    async def read_messages(self):
        try:
            async for raw in self.ws:
                try:
                    data = json.loads(raw)
                except (ValueError, UnicodeError):
                    log.warning("忽略无效 JSON 帧")
                    continue
                if not isinstance(data, dict):
                    continue
                echo = data.get("echo")
                if isinstance(echo, str) and echo in self.pending:
                    future = self.pending[echo]
                    if not future.done():
                        future.set_result(data)
                elif data.get("retcode") == 1403:
                    raise APIError("NapCat token 验证失败（1403），请核对 access_token")
                elif is_group_poke(data):
                    if self.online is False:
                        continue
                    if self.events.full():
                        log.warning("事件队列已满，丢弃本次 poke")
                    else:
                        self.events.put_nowait((time.monotonic(), data))
                elif data.get("meta_event_type") == "heartbeat":
                    status = data.get("status")
                    if isinstance(status, dict) and isinstance(status.get("online"), bool):
                        self.update_status(status)
        except Exception as exc:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(exc)
            raise
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(APIError("WebSocket 已断开，执行结果未知，不自动重试"))

    async def process_events(self, handler, self_id):
        while True:
            received, event = await self.events.get()
            # 网络/接口阻塞后不集中补发排队已久的通知。
            if (self.online is True
                    and time.monotonic() - received <= self.config.max_event_age_seconds):
                await handler.handle_poke_event(event, self_id, self.send_group_poke)

    async def session(self, handler):
        reader = asyncio.create_task(self.read_messages())
        worker = None
        monitor = None
        try:
            info = await self.call("get_login_info")
            self_id = qq_id(info.get("user_id")) if isinstance(info, dict) else None
            if self_id is None:
                raise APIError("get_login_info 未返回有效 user_id")
            if self.config.self_id is not None and self.config.self_id != self_id:
                raise APIError("登录 QQ 与配置 self_id 不一致，拒绝反戳")
            await self.check_status()
            if self.online:
                log.info("已连接，当前 QQ %s，开始监听所有群的戳一戳", self_id)
            worker = asyncio.create_task(self.process_events(handler, self_id))
            monitor = asyncio.create_task(self.monitor_connection())
            done, _ = await asyncio.wait((reader, worker, monitor), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            tasks = [t for t in (reader, worker, monitor) if t is not None]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


async def run(config, handler):
    headers = {"Authorization": f"Bearer {config.access_token}"} if config.access_token else {}
    while True:
        try:
            async with connect(config.ws_url, additional_headers=headers, proxy=None,
                               open_timeout=config.api_timeout_seconds,
                               ping_interval=20, ping_timeout=20, close_timeout=3,
                               max_size=16 * 1024 * 1024) as ws:
                await OneBotClient(ws, config).session(handler)
            log.warning("OneBot 连接已关闭，准备重连")
        except SessionReset as exc:
            log.info("%s", exc)
        except (OSError, TimeoutError, WebSocketException, APIError) as exc:
            log.error("OneBot 连接异常：%s", exc)
        # handler 在重连之间保留冷却和去重；旧队列随连接丢弃。
        await asyncio.sleep(config.reconnect_seconds)
