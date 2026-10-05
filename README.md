# SAYELF Platform Intelligence

本项目监测海内外自媒体平台公开的官方规则、算法说明、API 文档和产品公告，并保留来源快照、定位、哈希、时间与版本差异。分析按事实、推断、假设和行动分层，供人工复核。

当前目录覆盖 X、YouTube、Instagram、Facebook、Reddit、TikTok、小红书、视频号、抖音、公众号和哔哩哔哩。X 是首个完成端到端审核流程的平台；其余平台已提供来源适配器，但新取得的证据仍需语义审核后才能支持规则或行动。来源不可读取时，界面会显示来源入口和失败状态。

系统只读取公开官方网页，不登录或操作账号，不写帖子、不自动发布。核心运行时仅依赖 Python 标准库，要求 Python 3.11 或更新版本。

## 本机运行

在仓库根目录执行：

```powershell
python -m platform_intelligence.cli --data data serve --port 8768
```

浏览器打开 `http://127.0.0.1:8768`。数据库、证据快照和运行记录保存在本机 `data/` 目录，该目录已加入忽略清单。

检查到期的所有平台来源：

```powershell
python -m platform_intelligence.cli --data data monitor --platform all
```

检查由用户操作触发；网络请求只访问代码中登记并校验过的官方来源。

## 验证

```powershell
python -m unittest discover -s tests -v
```

测试使用合成数据和临时目录，不依赖实际账号或本机历史数据库。

## 证据边界

抓取到原文只证明来源可读取，不代表政策含义已核验。Policy/API 约束需要可定位的官方证据及审核；算法情报区分官方事实、研究、观察和假设。未审核的来源变化不能成为有效 Action。来源覆盖和访问状况会随平台变更。

Agent Ops 接收器通过可选的本机共享组件运行；该组件及其运行数据不包含在本仓库中。

## 许可

本仓库代码采用随仓库提供的 MIT License。
