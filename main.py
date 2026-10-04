import argparse
import asyncio
import logging
from pathlib import Path
import sys

from config import ConfigurationError, load_config
from instance import AlreadyRunningError, single_instance
from onebot import run
from poke import PokeHandler


class RedactToken(logging.Filter):
    def __init__(self, token):
        super().__init__()
        self.token = token

    def filter(self, record):
        if self.token:
            record.msg = record.getMessage().replace(self.token, "[REDACTED]")
            record.args = ()
        return True


def main():
    parser = argparse.ArgumentParser(description="NapCat QQ 群自动反戳")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    parser.add_argument("--check-config", action="store_true", help="只校验配置，不连接 QQ")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except ConfigurationError as exc:
        print(f"配置无效：{exc}", file=sys.stderr)
        return 2
    if args.check_config:
        print("配置校验通过（尚未验证连接及 QQ 登录）")
        return 0
    logging.basicConfig(level=logging.INFO if config.enable_logs else logging.ERROR,
                        format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
    for output in logging.getLogger().handlers:
        output.addFilter(RedactToken(config.access_token))
    try:
        with single_instance(args.config):
            asyncio.run(run(config, PokeHandler(config)))
    except AlreadyRunningError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except OSError:
        print("无法创建或使用运行锁，请检查配置目录的写入权限", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
