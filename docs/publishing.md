# 提交到 GitHub

仓库根目录应是包含 `main.py` 与本 README 的 `qq-auto-poke` 目录。不要将外层个人工作目录、QQ 或 NapCat 安装目录整体上传。

## 首次提交

在项目目录打开终端，先运行测试，再创建本地仓库：

```sh
git init
git add .
git status --short
git diff --cached --stat
git diff --cached --check
git commit -m "Initial release: QQ group auto poke back"
git branch -M main
```

提交前查看暂存文件及差异，确认仅包含源码、模板、测试和说明。`git commit` 如提示缺少作者信息，在本仓库设置自己的 `user.name` 与 `user.email` 后重新执行。

发布到自己的仓库时，在 GitHub 创建空仓库，使用页面给出的远程地址运行 `git remote add origin <仓库地址>`，再执行 `git push -u origin main`。

## 哪些内容不能公开

`.gitignore` 已排除默认 `config.yaml`、其他 `config.*.yaml`（保留模板）、`*.local.json`、日志、虚拟环境、运行锁、缓存和 NapCat 安装包等。

| 可以提交 | 留在本机 |
| --- | --- |
| Python 源码、测试 | 含 token / QQ 号的实际配置 |
| `config.example.yaml` | `config.yaml`、自定义私人配置 |
| `launcher.example.json` | `launcher.local.json` |
| Windows 源码启动脚本 | NapCat、QQ、可执行文件和 DLL |
| README、许可证、CI | 运行日志、扫码二维码、账号缓存 |

自定义配置若采用其他文件名，需要自行加入 `.gitignore`。Git 忽略规则不会移除已跟踪的文件：误暂存或已提交的私人文件使用 `git rm --cached -- <文件>` 从 Git 移除，本机文件会保留。公开过的 token 应立即更换，即使后来删除文件，它仍可能存在于历史提交中。

提交 Issue 的日志也应遮盖 token、QQ 号、群号、昵称和聊天内容。不要把本地诊断截图当作干净的发布素材。

## 自动测试

上传后 GitHub Actions 会在 Windows / Linux 和 Python 3.11 / 3.14 上执行单元测试及本地 WebSocket 集成测试。测试不需要 QQ 账号、NapCat 或 GitHub Secrets。Windows 任务还会检查 PowerShell 脚本语法。

本地通过仅表示本地环境验证完成，其他平台是否通过，以 GitHub Actions 实际结果为准。

## 后续版本发布

1. 在 `README.md` 与 `CHANGELOG.md` 更新版本号、日期、变更和已知限制。兼容旧配置的缺陷修复使用补丁版本，例如 `v1.0.0` → `v1.0.1`。
2. 运行测试、检查实际提交文件与差异，然后提交并推送到 `main`。等待本次提交对应的全部 GitHub Actions 任务通过。
3. 对通过验证的提交创建带说明的 Git 标签，再将标签推送到 GitHub。不要移动已发布的标签。
4. 创建同名 GitHub Release，说明修复内容、升级步骤与限制。附加仅包含公开源码的 ZIP，以及对应 SHA-256 校验文件；源码包应包含测试、模板和启动脚本。

从旧版升级时保留本地 `config.yaml`、`launcher.local.json` 和 Python 环境。发布包不能包含这些文件，也不能包含 QQ / NapCat 安装文件、运行日志或登录数据。
