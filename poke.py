"""反戳策略：不依赖 WebSocket，可注入任意发送函数。"""
import logging
import time

from config import qq_id

log = logging.getLogger("auto_poke")


def is_group_poke(event):
    return (isinstance(event, dict)
            and event.get("post_type") == "notice"
            and event.get("notice_type") == "notify"
            and event.get("sub_type") == "poke"
            and qq_id(event.get("group_id")) is not None)


class PokeHandler:
    def __init__(self, config, *, clock=time.monotonic, wall_clock=time.time):
        self.config = config
        self.clock = clock
        self.wall_clock = wall_clock
        self.cooldowns = {}
        self.seen = {}
        self.last_send = float("-inf")

    async def handle_poke_event(self, event, self_id, send_group_poke):
        if not is_group_poke(event):
            return False
        group, user, target, own = (
            qq_id(event.get(key)) for key in ("group_id", "user_id", "target_id", "self_id")
        )
        if own != self_id or target != self_id or user is None or user == self_id:
            return False
        stamp = event.get("time")
        # NapCat 必有秒级 time；缺失、异常或陈旧的事件不补发。
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
            return False
        try:
            age = self.wall_clock() - stamp
        except OverflowError:
            return False
        if not 0 <= age <= self.config.max_event_age_seconds:
            return False
        now = self.clock()
        self.seen = {k: v for k, v in self.seen.items() if v > now}
        self.cooldowns = {k: v for k, v in self.cooldowns.items() if v > now}
        # poke 没有标准唯一事件 ID。同秒、同群、同双方的通知保守合并。
        fingerprint = (own, group, user, target, stamp)
        pair = (own, group, user)
        if fingerprint in self.seen or pair in self.cooldowns:
            return False
        if now - self.last_send < self.config.global_interval_seconds:
            return False
        # 在 await 之前占位；失败也保留，绝不自动重试副作用请求。
        self.seen[fingerprint] = now + self.config.dedup_seconds
        self.cooldowns[pair] = now + self.config.cooldown_seconds
        self.last_send = now
        log.info("群 %s：用户 %s 戳了我", group, user)
        try:
            await send_group_poke(group, user)
        except Exception as exc:
            log.error("群 %s：自动戳回用户 %s 失败：%s", group, user, exc)
            return False
        log.info("群 %s：已自动戳回用户 %s（接口已确认）", group, user)
        return True
