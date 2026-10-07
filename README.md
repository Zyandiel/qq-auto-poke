# QQ 群自动反戳

[![Tests](https://github.com/Zyandiel/qq-auto-poke/actions/workflows/tests.yml/badge.svg)](https://github.com/Zyandiel/qq-auto-poke/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/Zyandiel/qq-auto-poke)](https://github.com/Zyandiel/qq-auto-poke/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

当前版本：**v1.0.2**。版本变化见 [CHANGELOG](CHANGELOG.md)。

其他群成员戳当前登录账号 → 收到群 poke 通知 → 在同一个群戳回发起者一次。

使用 **NapCatQQ + OneBot 11 正向 WebSocket + Python 3.11+**。Python 只有 `websockets` 和 `PyYAML` 两个运行依赖，无数据库、业务管理后台或 Docker。整个过程由事件驱动，不使用鼠标、截图或按键模拟。

## 为什么选 NapCat

截至 2026-10-04，NapCat 官方仓库仍有近期发布，提供 Windows 启动包，并明确实现群 poke 通知和发送接口。直接连接它的 WebSocket 即可，个人使用无需再引入应用框架。

- [NapCat 官方仓库](https://github.com/NapNeko/NapCatQQ)
- [官方下载与版本说明](https://github.com/NapNeko/NapCatQQ/releases)
- [官方 Shell 安装说明](https://napneko.github.io/guide/boot/Shell)

`group_poke` 是 NapCat 扩展接口，不保证其他 OneBot 11 实现支持。QQ 更新可能影响兼容性，安装时应核对所下载 Release 的说明。本项目不捆绑 QQ 或 NapCat。

## 项目结构

```text
qq-auto-poke/
├── main.py                 # 入口、日志及启动
├── config.py               # 配置读取与校验
├── poke.py                 # handle_poke_event：判断与防循环
├── onebot.py               # WS 通信、send_group_poke、断线重连
├── instance.py             # 防止同一配置重复启动
├── config.example.yaml     # 配置模板；config.yaml 由你本地创建
├── requirements.txt        # 固定运行依赖版本
├── scripts/windows/        # 可选的 Windows 双击启动脚本
├── docs/windows.md         # 保留正常 QQ 聊天窗口的配置
├── docs/publishing.md      # GitHub 提交和隐私检查
├── tests/                  # 策略测试与本地 WS 集成测试
├── .github/workflows/      # GitHub Actions 自动测试
├── CHANGELOG.md            # 版本记录与已知限制
└── LICENSE                 # 本项目源码使用 MIT
```

## 1. 准备 NapCat 和 QQ

先选一种运行方式：

- **需要像普通 QQ 一样聊天**：使用官方 Framework 原生加载方式，按 [Windows 启动说明](docs/windows.md) 配置。QQ 窗口与反戳程序共用同一登录会话。
- **只需要后台反戳**：从官方 Releases 下载 `NapCat.Shell.zip`，解压后按官方说明运行 `launcher.bat`；Windows 10 使用相应启动脚本。

安装与该 Release 兼容的 QQ / NTQQ 版本，扫码登录希望自动反戳的账号，完成手机验证。单独启动普通 QQ 不会提供 OneBot。保持 NapCat 及其 QQ 进程在线，账号须已加入目标群，通常无需群管理员身份。

从 NapCat 启动输出取得 WebUI 地址及登录 token。常见地址为 `http://127.0.0.1:6099/webui`，以启动输出为准。这个网页用于登录和配置 NapCat。

## 2. 配置 OneBot 正向 WebSocket

在 NapCat WebUI 的网络配置中新建 **WebSocket 服务端（正向 WS）**：

| 配置 | 建议值 |
| --- | --- |
| 名称 | `auto-poke` |
| 启用 | 开启 |
| Host | `127.0.0.1` |
| Port | `3001` |
| Token | 自行设置一段随机的 ASCII 字符串 |
| 消息格式 | `array`（不影响 poke 通知） |
| 心跳 | `30000` 毫秒 |

保存并确认服务已监听。不要选择 WebSocket 客户端 / 反向 WS。同机运行使用回环地址，无需开放公网端口。

在本项目目录复制模板：

```powershell
Copy-Item config.example.yaml config.yaml
```

修改新建的 `config.yaml`，将 `CHANGE_ME` 替换为刚设置的 **WS Token**：

```yaml
ws_url: "ws://127.0.0.1:3001"
access_token: "CHANGE_ME"
self_id: null
cooldown_seconds: 3
dedup_seconds: 30
global_interval_seconds: 1
max_event_age_seconds: 30
api_timeout_seconds: 10
reconnect_seconds: 3
healthcheck_seconds: 15
offline_reconnect_seconds: 60
enable_logs: true
```

WebUI 登录 token 与 OneBot WS token 是不同配置。`6099` 通常是网页管理端口，Python 要连实际 WS 端口。连接根路径，不加 `/api`，因为 NapCat 的 `/api` 连接不推送事件。

`self_id: null` 通过 `get_login_info` 自动取得当前 QQ；填写 QQ 号时会核对登录账号，不一致则拒绝反戳。时间单位为秒且必须大于 0。`enable_logs: false` 关闭常规日志，保留错误。只有服务端也未设 token 时才使用空字符串。修改配置后重启 Python。

`config.yaml` 是私人文件，已被 Git 忽略。不要用真实 token 修改公开的 `config.example.yaml`。

## 3. 安装并启动 Python 程序

从 [最新 Release](https://github.com/Zyandiel/qq-auto-poke/releases/latest) 下载源码 ZIP 并解压，或者克隆仓库：

```sh
git clone https://github.com/Zyandiel/qq-auto-poke.git
cd qq-auto-poke
```

安装 Python 3.11 或更新版本，在此 README 所在目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --check-config
.\.venv\Scripts\python.exe main.py
```

无需激活虚拟环境。系统找不到 `python` 时，安装 Python 并加入 PATH，或用 `py -3` 创建虚拟环境。`--check-config` 只校验本地配置，不连接 QQ。

Windows 也可使用 [双击启动脚本](docs/windows.md)，在保留 QQ 聊天窗口的同时启动反戳。

Linux / macOS 安装好对应平台 NapCat 后：

```sh
cp config.example.yaml config.yaml
# 先编辑 config.yaml，设置 WS 地址和 token
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --check-config
.venv/bin/python main.py
```

自定义配置使用 `python main.py --config path/to/config.yaml`，默认读取 `main.py` 同目录的配置。前台运行按 `Ctrl+C` 退出。

同一个配置文件只能启动一个进程，重复启动会提示并退出。两个不同配置仍可独立运行，因此同一个 QQ 应只保留一个反戳进程。

## 4. 验证反戳效果

1. 等待日志出现 `已连接，当前 QQ ...，开始监听所有群的戳一戳`，核对登录账号。
2. 让另一位共同群成员在群里对你使用“戳一戳”。
3. 查看日志，并在 QQ 群中确认你戳回了对方：

```text
[19:20:13] 群 123456：用户 987654 戳了我
[19:20:13] 群 123456：已自动戳回用户 987654（接口已确认）
```

4. 自己戳别人、自己戳自己、别人戳其他人、私聊 poke 均不触发。
5. 同一人在同一群的 3 秒冷却内连续戳你，最多回一次；等待冷却后再戳，应再次响应。
6. NapCat 断开后，Python 应打印断线信息并重连；旧连接的排队事件不会集中补发。

“接口已确认”表示 NapCat 返回 `status=ok` 且 `retcode=0`，最终展示仍需在真实群里确认。测试使用本地模拟服务，不登录 QQ，不戳真实用户。

## 真实协议与字段

群 poke 通知的最小示例，所有号码均为示例：

```json
{
  "time": 1791112813,
  "self_id": 111111,
  "post_type": "notice",
  "notice_type": "notify",
  "sub_type": "poke",
  "group_id": 222222,
  "user_id": 333333,
  "target_id": 111111
}
```

| 字段 | 群 poke 中的含义 |
| --- | --- |
| `self_id` | 当前 NapCat 登录账号 |
| `group_id` | 发生通知的群 |
| `user_id` | 发起戳一戳的人 |
| `target_id` | 被戳的人 |
| `time` | NapCat 构造事件时的 Unix 秒级时间 |
| `raw_info` | 可选原始提示内容，本工具不依赖 |

要求事件类型完全匹配，群号和账号有效，事件 `self_id` 与实际登录账号一致，且 `target_id == self_id`、`user_id != self_id`。群事件不使用私聊通知中的 `sender_id`。

实际发送请求是：

```json
{
  "action": "group_poke",
  "params": {"group_id": "222222", "user_id": "333333"},
  "echo": "每个请求唯一的标识"
}
```

发送参数 `user_id` 是要戳回的对象，取自事件发起人。Python 方法 `send_group_poke` 内部调用真实的 `group_poke` action。

协议核对基准：NapCat 提交 `26d7533e0f5800fdff865ab2f2ad7692917e1076`（2026-09-29）：

- [事件字段 OB11PokeEvent.ts](https://github.com/NapNeko/NapCatQQ/blob/26d7533e0f5800fdff865ab2f2ad7692917e1076/packages/napcat-onebot/event/notice/OB11PokeEvent.ts)
- [群事件构造 parsePaiYiPai](https://github.com/NapNeko/NapCatQQ/blob/26d7533e0f5800fdff865ab2f2ad7692917e1076/packages/napcat-onebot/api/group.ts)
- [发送实现 SendPoke.ts](https://github.com/NapNeko/NapCatQQ/blob/26d7533e0f5800fdff865ab2f2ad7692917e1076/packages/napcat-onebot/action/packet/SendPoke.ts)
- [接口注册 router.ts](https://github.com/NapNeko/NapCatQQ/blob/26d7533e0f5800fdff865ab2f2ad7692917e1076/packages/napcat-onebot/action/router.ts)
- [WS 鉴权与事件推送](https://github.com/NapNeko/NapCatQQ/blob/26d7533e0f5800fdff865ab2f2ad7692917e1076/packages/napcat-onebot/network/websocket-server.ts)
- [通知时间生成](https://github.com/NapNeko/NapCatQQ/blob/26d7533e0f5800fdff865ab2f2ad7692917e1076/packages/napcat-onebot/event/OneBotEvent.ts) 与 [服务器对时实现](https://github.com/NapNeko/NapCatQQ/blob/26d7533e0f5800fdff865ab2f2ad7692917e1076/packages/napcat-core/helper/server-time.ts)
- [官方 API](https://napneko.github.io/onebot/api)、[网络配置](https://napneko.github.io/config/basic)

## 防循环与失败处理

- 忽略自己发起的 poke，戳回后的通知也会被过滤。
- 同一账号、同一群、同一发起人默认冷却 3 秒。
- 默认保留 30 秒指纹，合并相同 `self_id/group_id/user_id/target_id/time` 的事件。poke 没有标准唯一 ID，同一秒重复戳会保守合并。
- 全局默认每秒至多发起一次反戳，超出时跳过，多群同时被戳也受此限制。
- 有界事件队列、单消费者、过时事件过滤，发送前登记冷却和去重。
- API 失败或超时记录原因，不自动重试。超时可能已经执行，补发会有重复戳风险。
- 重连会重新核对账号，并保留本进程的冷却和去重状态；退出进程后内存状态清空。
- 定期调用 `get_status` 检查应用接口和账号状态，不仅检查 WebSocket ping / pong。接口不响应时重建连接。
- QQ 离线时暂停反戳并丢弃事件；恢复在线后刷新监听连接并重新核对账号，不补发离线期间的通知。

如果对方也是自动反戳程序且延迟超过冷却，仍可能周期性互戳。可增大冷却，或在策略入口排除该账号。没有持久存储，不承诺跨进程重启严格只发送一次。

## 电脑断网、休眠后恢复

从 v1.0.0 / v1.0.1 升级到 v1.0.2 时，退出旧的 Python 反戳程序，更新源码后重新启动即可。保留原有 `config.yaml`、虚拟环境及 `launcher.local.json`；v1.0.1 引入的状态检查配置项未填写时使用默认值，v1.0.2 不增加配置项，运行依赖不变。使用 Windows 启动脚本时可通过 `scripts/windows/restart.cmd` 切换到更新后的源码。

Python 连接的是本机 NapCat，电脑互联网断开时，本机 WS 可能一直保持连接，QQ 却已离线。`get_login_info` 还能返回缓存的 QQ 号，并不能证明账号在线。本工具启动时和运行中都会用 `get_status` 核对状态。

- `healthcheck_seconds` 默认 15 秒：定期检查接口和在线状态。API 超时按 `api_timeout_seconds` 处理，然后自动重连。
- `offline_reconnect_seconds` 默认 60 秒：持续离线达到该时长后刷新 OneBot 连接，避免长期停在旧监听会话。不会重启 QQ 或 NapCat。
- 从离线变为在线时打印 `QQ 已恢复在线，正在重新建立监听会话`，重连及校验通过后再次打印 `开始监听所有群的戳一戳`。
- 离线状态未改变时，不为每个 heartbeat 重复打印警告；持续离线的连接刷新仍会记录。

v1.0.2 修复了接口显示在线、收到新通知却因时钟偏差不反戳的问题。NapCat 会对自己的通知时间做服务器对时，休眠或断线后该时间可能与 Python 的本机时间不同。本工具以同一连接中新生成、账号匹配的生命周期 / 心跳建立通知时间基准，用单调时钟推算事件年龄；每条通知保留到达时的基准。偏差明显时会打印“NapCat 通知时钟与本机相差约 ... 秒”。没有可信基准时沿用本机时间，不使用 poke 自身校准。事件过期、队列过期、冷却和去重限制仍然生效，无需增大 `max_event_age_seconds`。若仍出现“收到戳我的群通知，但事件时间不在有效范围”，检查心跳配置和 NapCat 日志。

如果恢复网络后 QQ 可以聊天，但 NapCat 仍报告离线或一直不推送群事件，问题可能在 NapCat 内部。仅重连 Python 无法保证修复；官方仓库也有 [WS 存活但账号静默离线的报告](https://github.com/NapNeko/NapCatQQ/issues/2071)。可先重启 Python；仍无效时从 QQ 托盘退出 QQ，再通过带 NapCat 的入口重新打开，按需完成登录。不要只打开普通 QQ。

本工具不会自动强制关闭聊天窗口，也不会反复调用 `set_restart`。在上述协议核对版本的官方 Framework 加载方式中，重启回调可能未初始化，而 Shell 有独立的重启实现；不能把这个接口当作通用的无感恢复。QQ 要求扫码或手机验证时仍需本人完成。

## 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 找不到配置文件 | 先复制 `config.example.yaml` 为 `config.yaml`，检查 `--config` 路径。 |
| 配置无效 | 修改 `CHANGE_ME`，YAML 缩进用空格，对照模板检查字段。诊断不会回显配置全文或 token。 |
| 提示同一配置已运行 | 退出原来的反戳进程再启动；遗留 `.lock` 文件本身不表示进程在运行，不需要删除。 |
| 连接拒绝 / WinError 10061 / 1225 | 启动 NapCat，启用正向 WS，核对 host / port，不要填 WebUI 的 6099。 |
| `1403` / 401 / 403 | 两端 WS token 必须一致，不能填 WebUI 登录密码，改完重启 Python。 |
| `get_login_info` 超时 | 检查 QQ 已登录、所连的是 WS 端口，以及 QQ 与 NapCat 版本是否匹配。 |
| 当前 QQ 不一致 | 登录目标账号，修正 `self_id`，或设为 null 跟随实际登录账号。 |
| 已连接却无反戳 | 用其他账号在群内戳你；检查 `/api` 路径、冷却、NapCat 通知与时间诊断日志，参照上面的恢复说明。 |
| 断网恢复后持续显示离线 | 新版会定期检查并刷新监听；QQ 能聊天但仍无群事件时，参照上面的恢复说明重新启动 NapCat。 |
| 两个账号都开自动反戳 | 冷却通常能中断快速互戳；回复间隔超过冷却时仍可能持续。可增大冷却或扩展账号过滤，当前没有配置式黑名单。 |
| `1404` / 不支持的 API | 确认连接的是支持 `group_poke` 的 NapCat，核对实际版本。 |
| `packetBackend发包能力不可用` | 群 poke 依赖 PacketBackend；核对 QQ / NapCat 版本、启动日志和官方高级配置，然后重启。 |
| 成功日志但 QQ 没显示 | 日志只表示 API 返回成功，在双方客户端检查效果及 NapCat / QQ 状态。 |
| 发送超时 | 结果未知，不会补发；检查日志，等待冷却后人工再戳一次。 |
| 依赖安装失败 | 确认 Python ≥ 3.11、能访问 PyPI，并用同一个虚拟环境安装和运行。 |
| 双击窗口一闪而过 | 使用本项目保留错误窗口的脚本，详见 Windows 说明。 |
| 关闭终端后停止 | 前台运行须保持终端、NapCat 和 QQ 在线；Windows 脚本可后台运行 Python。 |

[PacketBackend 官方说明](https://napneko.github.io/config/advanced) 的版本表可能滞后，优先查看具体 Release 说明及启动日志。

## 测试与扩展

在项目目录运行测试，无需 QQ：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖事件回环、私聊与无关通知、异常字段、冷却、去重、限速、API 错误 / 超时 / 断线、鉴权、账号核对、重连、配置隐私及进程锁；还覆盖 WS 未断但 QQ 离线、心跳 / 轮询恢复、应用接口假活以及离线事件不补发。时间校验测试包含来源时钟快 / 慢约 10 小时、本机时间跳变、跨秒通知、排队期间来源时间跳变，以及离线恢复后重建时间基准并拒绝旧通知。GitHub Actions 配置为 Windows / Linux、Python 3.11 / 3.14，上传后自动执行。

扩展入口是 `PokeHandler.handle_poke_event`：群开关和名单过滤放在账号校验后，统计放在接受事件后，随机延迟放在冷却登记后、发送前。加入延迟时须考虑事件过期和全局间隔。框架适配独立在 `OneBotClient.send_group_poke`。

## 贡献、许可证与发布

本项目原创源码采用 [MIT 许可证](LICENSE)。QQ、NapCat 及 Python 依赖分别遵循自身许可，不在本项目许可范围内。

提交改动参阅 [CONTRIBUTING](CONTRIBUTING.md)，隐私问题参阅 [SECURITY](SECURITY.md)。准备公开仓库时按 [发布说明](docs/publishing.md) 检查；只上传项目源码，排除账号配置、日志、二维码、缓存及第三方安装包。
