# 配置与安全问题

`config.yaml` 包含 OneBot access token，仅在本机使用。`*.local.json`、运行日志、锁文件和外部 QQ / NapCat 安装内容均不属于公开源码。

发现 token 泄露时，立即更改 NapCat 的 WS token 并同步修改本机配置；仅删除文件不能撤回已经公开的凭据。

提交安全问题时，不要在公开 issue 中附带凭据或真实账号数据。如果仓库已开启 GitHub 私密漏洞报告，可使用仓库的 Security 页面；否则先提交不含敏感内容的问题摘要。

本工具默认连接本机 `127.0.0.1`，使用 token 鉴权。远程部署时应使用可信的 WSS 或受保护的网络，不要把不带鉴权的 OneBot 服务暴露到公网。
