# Windows：正常聊天并保持自动反戳

Python 小工具只依赖 OneBot 服务。要保留普通 QQ 的聊天界面，可以使用兼容的 NapCat Framework，再用本项目的 Windows 启动脚本同时启动反戳程序。只需要无界面运行时，按 README 使用 NapCat Shell，并直接启动 Python 即可。

## 先确认 NapCat 与 QQ 版本

NapCat Framework 的加载器随版本变化。本项目的 `scripts/windows/start.ps1` 适配解压目录中含 `napimain.exe`、`napiloader.dll`、`nativeLoader.cjs`、`napcat.mjs` 的官方 Framework 包，使用其原生加载器启动 QQ，不修改 QQ 安装文件。

优先阅读 [NapCat 官方 Framework 说明](https://napneko.github.io/guide/boot/Framework) 和 [官方 Releases](https://github.com/NapNeko/NapCatQQ/releases) 的对应版本说明。官方文档目前提示近期 QQ 与 LiteLoader 的兼容性问题，并鼓励使用 Shell；不要把 Framework 对某一 QQ 版本的成功启动当作对所有版本的保证。这里的启动脚本也不适配另一种 `NapCatWinBootMain.exe` Shell 加载器。

Framework 的 [官方 nativeLoader.cjs 源码](https://github.com/NapNeko/NapCatQQ/blob/main/packages/napcat-framework/nativeLoader.cjs) 可用于核对加载入口。安装包若没有上述文件，请使用该版本自带的官方启动方式；OneBot 就绪后单独启动 Python，不要为了满足文件检查重命名其他加载器。

本仓库不包含 QQ、NapCat、扫码图、登录凭据或其他二进制文件。请自己从官方来源下载并解压；无需把它们放进项目目录。

## 首次设置

1. 在本项目根目录安装 Python 环境和依赖。具体 Python 版本要求见 README。

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   Copy-Item config.example.yaml config.yaml
   ```

2. 按 README 配置 NapCat 的正向 WebSocket 与本项目 `config.yaml`。地址和 token 必须对应；QQ 号默认自动取得。不要把 `config.yaml` 提交到 GitHub。

3. 在 `scripts/windows` 中复制 `launcher.example.json` 为 `launcher.local.json`，填写两个路径：

   - `qq_path`：实际 `QQ.exe` 的文件路径。
   - `napcat_framework_dir`：包含上面四个文件的官方 Framework 解压目录。
   - `napcat_workdir`：可选。留为 `null` 或省略时，使用 Framework 目录；希望沿用现有 NapCat 的 OneBot 配置时，填写现有工作目录，脚本通过 `NAPCAT_WORKDIR` 使用它，不复制账号配置。

   路径可以为绝对路径，也可以相对于 `launcher.local.json` 所在目录。JSON 中推荐使用 `/`；使用 `\` 时需要写成 `\\`。示例中的 `../../../local/...` 只是演示相对路径，并不代表已安装这些软件。`launcher.local.json` 已被 Git 忽略。

4. 双击 `scripts/windows/check.cmd`。它仅检查启动 JSON、Python 可执行文件和必需文件是否存在；不会启动或停止 QQ，不读取 token，也不能证明版本兼容、依赖完整或账号已登录。需要校验 Python 配置时，在项目目录执行：

   ```powershell
   .\.venv\Scripts\python.exe main.py --check-config
   ```

## 日常操作

- 双击 `scripts/windows/start.cmd`：启动普通 QQ 窗口中的 NapCat Framework，并启动本项目 Python 程序。首次启动按 QQ 提示登录；反戳程序会等待 OneBot 就绪并自动连接。
- 双击 `scripts/windows/logs.cmd`：持续查看 `runtime.log`。看到“开始监听”后，请另一位成员在共同群中戳你一次，并核对群内的反戳提示。用 `Ctrl+C` 退出日志查看。
- 双击 `scripts/windows/stop.cmd`：只停止当前项目的 Python 反戳程序，也包含 Windows 虚拟环境启动的实际 Python 子进程。QQ 与 NapCat 仍运行，可以继续聊天；退出 QQ 请使用 QQ 自己的托盘菜单。
- 双击 `scripts/windows/restart.cmd`：重新启动本项目的 Python 反戳程序，保留 QQ 与 NapCat。更新源码或希望手动刷新监听时使用。

已加载同一路径 `napiloader.dll` 的 QQ 主进程会被识别并复用；QQ 的 renderer/GPU 子进程无需全部加载 DLL。官方 `napimain.exe` 在注入后可能退出，脚本因此检查 QQ 内加载的 DLL，不以加载器是否仍运行判断。重复启动也会检查当前项目的 Python 进程：只匹配首个脚本参数为本项目 `main.py` 完整路径的 `python.exe` / `pythonw.exe`，包含虚拟环境 redirector 与实际 worker，不限定解释器安装路径。

仅检测到未注入当前加载器的 QQ 进程（例如普通 QQ、另一份 Framework 或 Headless/Shell）时，脚本会提示先退出，不会替你强制结束。不要同时为同一个 QQ 账号启动两种模式。若所有模块检查因权限失败，也会提示先退出现有 QQ；建议让 QQ 和启动脚本以同一普通用户身份运行。

只想沿用自己已启动的 OneBot，单独启动反戳程序：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\manage.ps1 -Action Start
```

## 排查

| 提示或现象 | 处理 |
| --- | --- |
| `Missing .venv` | 在项目根目录执行上面的环境与依赖安装命令。不要把别人的虚拟环境直接复制过来。 |
| `Copy launcher.example.json...` | 创建本地 JSON 并填实际路径。 |
| `Required file missing` | 检查路径、是否完整解压及 Framework 包的加载器版本。 |
| `Invalid launcher JSON` | 检查引号、逗号及反斜杠，路径优先用 `/`。 |
| 普通 QQ / Headless 正在运行 | 自己从对应托盘或终端退出，再双击启动；脚本不会结束 QQ。 |
| 启动窗口闪退 | 从 PowerShell 执行 `start.ps1 -Check` 看错误；`.cmd` 默认保留窗口，源码使用 CRLF 换行。 |
| QQ 出现但反戳一直重连 | 检查 NapCat 是否成功加载、已登录、正向 WebSocket 是否开启及地址/token 是否一致。 |
| Python 立即退出 | 查看项目 `runtime.log` 和 `runtime.stdout.log`，重新安装依赖或校验配置。 |
| 只有加载器启动提示，没有 QQ | 检查项目 `logs/napcat-launch.stderr.log` 和对应官方版本说明；文件存在检查不会验证 DLL 与 QQ 是否兼容。 |

PowerShell 脚本兼容 Windows PowerShell 5.1；`.cmd` 使用系统 `powershell.exe`。启动脚本只影响本次进程的环境变量，不写入系统环境变量。日志会包含群号和成员 QQ 号，应保留在本机，不上传 GitHub。

电脑断网或休眠后，新版 Python 会定期调用 `get_status`，在 QQ 恢复时刷新监听连接。若 QQ 能聊天，但一直没有群事件，可先使用 `restart.cmd`；仍无效时退出 QQ，再用 `start.cmd` 重新加载 NapCat。仅重启 Python 不能保证修复 NapCat 内部的事件监听故障。QQ 要求重新登录时请按提示完成。
