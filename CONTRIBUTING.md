# 参与开发

使用 Python 3.11+，安装 `requirements.txt` 后运行：

```sh
python -m unittest discover -s tests -v
```

自动化测试使用本地模拟 OneBot 服务，不需要真实 QQ、token 或群。修改事件条件、冷却、回包处理等行为时，请补充相应测试。

提交问题请说明操作系统、Python / QQ / NapCat 版本、期望行为与实际行为。日志须删去真实 token、账号、群号及聊天内容。不要上传 `config.yaml`、登录二维码、NapCat 缓存或完整 QQ 日志。

Python 反戳策略放在 `poke.py`，协议适配放在 `onebot.py`。保持两个运行依赖和内存状态，不引入数据库或业务后台。
