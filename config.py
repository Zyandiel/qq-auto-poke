"""配置读取与启动前校验。"""
from dataclasses import dataclass, fields
from pathlib import Path
import math
from urllib.parse import urlsplit

import yaml


class ConfigurationError(ValueError):
    """仅包含可安全打印的配置诊断，不含 YAML 原文或配置值。"""


def qq_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    try:
        text = str(value)
        if len(text) > 20 or not text.isascii() or not text.isdigit():
            return None
        number = int(text)
    except ValueError:
        return None
    return number if number > 0 else None


@dataclass(frozen=True)
class Config:
    ws_url: str = "ws://127.0.0.1:3001"
    access_token: str = ""
    self_id: int | None = None
    cooldown_seconds: float = 3
    dedup_seconds: float = 30
    global_interval_seconds: float = 1
    max_event_age_seconds: float = 30
    api_timeout_seconds: float = 10
    reconnect_seconds: float = 3
    enable_logs: bool = True


def load_config(path):
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError("无法读取 UTF-8 配置文件，请检查 --config 路径") from exc
    except (yaml.YAMLError, ValueError) as exc:
        raise ConfigurationError("YAML 语法错误，请检查缩进、引号，并使用空格") from exc
    if not isinstance(data, dict):
        raise ConfigurationError("配置必须是 YAML 键值表")
    unknown = set(data) - {f.name for f in fields(Config)}
    if unknown:
        raise ConfigurationError("包含未知配置项，请对照 config.example.yaml 检查字段名")
    cfg = Config(**data)
    if not isinstance(cfg.ws_url, str):
        raise ConfigurationError("ws_url 必须是字符串")
    try:
        url = urlsplit(cfg.ws_url)
        port = url.port
    except ValueError as exc:
        raise ConfigurationError("ws_url 的主机或端口格式无效") from exc
    if (url.scheme not in ("ws", "wss") or not url.hostname
            or url.username or url.password or url.query or url.fragment):
        raise ConfigurationError("ws_url 必须为 ws:// 或 wss:// 地址，token 请单独配置")
    if port is not None and not 1 <= port <= 65535:
        raise ConfigurationError("WebSocket 端口不合法")
    if url.path.rstrip("/") == "/api":
        raise ConfigurationError("/api 连接不推送事件，请使用根路径")
    if (not isinstance(cfg.access_token, str)
            or any(not 32 <= ord(c) < 127 for c in cfg.access_token)):
        raise ConfigurationError("access_token 必须是可打印 ASCII 字符串，不能含换行")
    if cfg.access_token == "CHANGE_ME":
        raise ConfigurationError("请将 access_token 改成 NapCat WS 服务端的 token")
    if cfg.self_id is not None:
        own = qq_id(cfg.self_id)
        if own is None:
            raise ConfigurationError("self_id 必须为正整数 QQ 号或 null")
        data["self_id"] = own
    for f in fields(Config):
        if f.name.endswith("_seconds"):
            value = getattr(cfg, f.name)
            try:
                valid = (not isinstance(value, bool) and isinstance(value, (float, int))
                         and math.isfinite(value) and value > 0)
            except OverflowError:
                valid = False
            if not valid:
                raise ConfigurationError(f"{f.name} 必须是大于 0 的有限数字")
    if not isinstance(cfg.enable_logs, bool):
        raise ConfigurationError("enable_logs 必须为 true 或 false")
    return Config(**data)
