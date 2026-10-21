CC Switch Droid Hook

English documentation: README.md
简体中文说明与使用方法：README.zh-CN.md
版本修改记录：CHANGELOG.md
启动入口：Open-Hook.cmd
配置模板：config.example.json

使用前从托盘完整退出 CC Switch；如有旧版 Addon 助手，也需先停止。
首次运行没有 config.json 时，会打开配置窗口：
选择 CC Switch 程序目录，填写 Droid / Factory API Key，点击“保存并启动”。
已有配置会直接使用。项目自带 Python，无需安装系统 Python。

通过本入口启动才会加载 Droid 功能，普通原版入口不会自动介入。
完整退出原版后，会话助手完成收尾并退出。

Droid 用量来自会话累计值的增量，可能包含多次请求，不导入对话正文。
速度只补全能够可靠匹配的记录；具体统计口径与限制见 README.zh-CN.md。

分享项目时，不包含个人 config.json、配置临时文件或 data 目录。
移除项目不会删除原版数据库中已导入的 Droid 历史用量。
