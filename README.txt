CC Switch Droid 插件
====================

功能
  - CC Switch 左侧多一个「Droid」入口：显示 Factory 额度（5 小时 / 每周 / 每月剩余、
    重置倒计时）和今日 Droid 用量。
  - 把 Droid 的 token 用量写进 CC Switch 的「用量统计」，带近似速度。
  - 「用量统计」页的筛选栏多一个 Droid 图标，点一下只看 Droid 的数据，再点一下（或点「全部」）取消。
  - 不修改 cc-switch.exe，CC Switch 升级后通常不用重装。

日常使用
  正常打开 CC Switch 就行。插件开机后在后台自动运行（没有窗口），
  检测到 CC Switch 打开后几秒内注入 Droid 入口。

安装（新电脑）
  0. 先装好 CC Switch 和 Droid，各自至少打开过一次。
  1. 把整个文件夹复制到固定位置（之后不要再移动；移动了就重新运行 install.cmd）。
     不要复制 data\sync_state.json（它记录的是旧电脑的同步进度）；config.json 可以一起复制。
  2. 双击 install.cmd：
     - 输入 Factory API key（可直接回车跳过，之后在 config.json 填 factoryApiKey）。
       创建地址：https://app.factory.ai/settings/api-keys
     - 弹出管理员授权时点「是」：给 cc-switch.exe 写入 WebView2 调试端口参数，
       以后 CC Switch 一启动就能被注入。
       点「否」也能用：插件会在 CC Switch 刚启动时自动带参数重启它一次（窗口会闪一下）。
     - 自动添加开机启动项并在后台运行。

卸载
  双击 uninstall.cmd（可选择是否删除已导入的 Droid 用量记录），然后删除文件夹。

用量多久写入一次
  CC Switch 只从自己的数据库读取用量，不认识 Droid 的会话文件，
  所以插件要把 Droid 的用量写进 CC Switch 数据库，「用量统计」才看得到。
  写入间隔跟随 CC Switch「用量统计」页右上角的「自动刷新」设置（5 / 10 / 30 / 60 秒）；
  设为「关闭」时每 60 秒写入一次。点 CC Switch 的「立即同步」也会马上写入一次。
  CC Switch 没打开时照样会写入。

config.json 设置说明
  修改后保存即可，约 10 秒内自动生效（debugPort 除外，见下）。
  注意：JSON 里的路径要把 \ 写成 \\，例如 "D:\\Data\\cc-switch.db"。

  factoryApiKey             Factory API key，用来获取额度。
                            留空时依次尝试：环境变量 FACTORY_API_KEY、~\.factory\.env 里的 FACTORY_API_KEY。
                            都没有时，Droid 页面会提示去填写。

  debugPort                 默认 9333。插件通过这个本机端口连接 CC Switch 的界面。
                            只有和其他程序端口冲突时才需要改；改完要重新运行 install.cmd
                            （更新管理员策略里的端口），并重启 CC Switch。

  quotaRefreshSeconds       默认 60。每隔多少秒向 Factory 请求一次额度，最小 15。
                            请求失败（如限流）时会自动延长到至少 120 秒再试。
                            Droid 页面右上角的「立即刷新」可以随时手动刷新。


  autoRestartWithoutPolicy  默认 true。没有写入管理员策略、CC Switch 又没开调试端口时，
                            是否由插件自动把它带参数重启一次。
                            保护措施：只重启刚启动不到 5 分钟的 CC Switch；10 分钟内最多 2 次。
                            设为 false 后不会自动重启，Droid 入口要等你自己用带端口的方式启动才出现。

  ccSwitchDbPath            CC Switch 数据库的位置。留空 = 默认的 ~\.cc-switch\cc-switch.db。
                            只有 CC Switch 的数据目录不在默认位置时才需要填写。

  droidSessionsDir          Droid 会话记录所在的文件夹。留空 = 默认的 ~\.factory\sessions。
                            只有 Droid 的数据目录不在默认位置时才需要填写。

文件
  install.cmd / uninstall.cmd   安装 / 卸载
  config.json                   设置（见上）
  data\addon.log                运行日志，出问题时先看这里
  data\sync_state.json          用量同步进度；删掉会把已有会话重新导入一遍（造成重复）
  addon\                        插件程序；修改 addon\inject.js 后会自动重新加载
  python\                       便携版 Python 3.12，不依赖电脑上的 Python

需要的条件
  Windows 10/11、Droid（~\.factory）、CC Switch 3.x。

注意
  - 调试端口只监听 127.0.0.1，外网访问不到，但本机其他程序可以通过它控制 CC Switch 界面。
  - Droid 入口和筛选按钮都是界面叠加层，不能在里面管理供应商或切换配置。
  - 成本按 CC Switch 价格表里的 API 价格估算，不等于 Factory 实际扣的额度。
  - 如果 CC Switch 大改界面导致入口消失，查看 data\addon.log，通常只需调整 addon\inject.js。
