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

随后在 GitHub 创建空仓库。使用页面给出的远程地址运行 `git remote add origin <仓库地址>`，再执行 `git push -u origin main`。整理和测试不代表已经替你创建或上传远程仓库。

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
