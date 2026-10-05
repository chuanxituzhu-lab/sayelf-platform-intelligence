<p align="center">
  <img src="platform_intelligence/static/logo.png" alt="SAYELF 山野精灵 logo" width="220">
</p>

<h1 align="center">SAYELF Platform Intelligence</h1>

<p align="center">
  <a href="https://github.com/chuanxituzhu-lab/sayelf-platform-intelligence/releases/latest">⬇️ Download latest release · 下载最新版本</a>
  · <a href="https://github.com/chuanxituzhu-lab/sayelf-platform-intelligence/releases">All releases · 全部版本</a>
</p>

**海内外自媒体平台官方情报工具。** 监测规则、算法说明、API 文档和产品变化，保留可定位的来源、快照、哈希、时间和版本差异，并把经审核的证据整理成可复制简报。

**Official intelligence for global creator platforms.** Track public policies, algorithm documentation, APIs, and product updates. Preserve locatable sources, snapshots, hashes, timestamps, and version diffs, then compile reviewed evidence into a copyable brief.

## 功能 · Features

- 覆盖 X、YouTube、Instagram、Facebook、Reddit、TikTok、小红书、视频号、抖音、公众号和哔哩哔哩；支持中英文界面与简报。
- Monitor 11 platforms: X, YouTube, Instagram, Facebook, Reddit, TikTok, Xiaohongshu, WeChat Channels, Douyin, WeChat Official Accounts, and Bilibili. The interface and generated briefs support Chinese and English.
- 官方来源快照、定位文本、哈希、历史版本和正文 Diff，支持回溯每条结论的依据。
- Keep official-source snapshots, text locators, hashes, version history, and diffs so conclusions can be traced to evidence.
- 按 FACT → PHENOMENON → RELATION → MECHANISM → BOUNDARY → IMPACT → ACTION → MEASURE 组织分析，并区分事实、推断、观察和假设。
- Structure analysis from FACT → PHENOMENON → RELATION → MECHANISM → BOUNDARY → IMPACT → ACTION → MEASURE, while keeping facts, inferences, observations, and hypotheses distinct.
- X 已跑通首个端到端审核样板；其他平台适配器已接入，新增快照仍需语义审核后才能支持有效结论或行动。
- X is the first end-to-end reviewed vertical slice. Other platform adapters are connected; new snapshots require semantic review before they can support active conclusions or actions.
- 仅读取公开官方来源；不登录、操作账号、生产帖子或自动发布。
- Reads public official sources only. It does not log in to or operate accounts, create posts, or publish automatically.

## 快速开始 · Quick start

需要 Python 3.11 或更新版本；核心运行时仅使用 Python 标准库。

Requires Python 3.11 or newer. The core runtime uses only the Python standard library.

```powershell
python -m platform_intelligence.cli --data data serve --port 8768
```

打开 `http://127.0.0.1:8768`，点击页眉的 English / 中文切换语言。检查到期的所有来源：

Open `http://127.0.0.1:8768` and switch languages from the header. Check all sources that are due:

```powershell
python -m platform_intelligence.cli --data data monitor --platform all
```

检查由用户操作触发；运行记录、数据库和证据快照保存在本机 `data/` 目录，不应提交到 Git。

Checks are user-triggered. Run history, the database, and evidence snapshots stay in the local `data/` directory and should not be committed to Git.

## 验证 · Validation

```powershell
python -m unittest discover -s tests -v
```

测试使用合成数据和临时目录，不依赖真实账号或本机运行数据库。 · Tests use synthetic data and temporary directories; they do not require real accounts or the local runtime database.

## 证据边界 · Evidence boundaries

获取到原文不等于审核通过。Policy/API 硬约束必须有可定位的官方证据并完成审核；算法情报明确区分官方事实、研究、观察和假设。英文界面会翻译已审核的内置 X 行动文案；未配置翻译的官方原文和证据引文保留来源语言。

Capturing a source does not constitute approval. Policy/API hard constraints require locatable official evidence and review. Algorithm intelligence separates official facts, research, observations, and hypotheses. The English interface translates the reviewed built-in X actions; official source text and evidence quotations without an approved translation remain in their original language.

Agent Ops 接收器依赖可选的本机共享组件；该组件和本地运行数据不包含在此仓库中。

The optional Agent Ops receiver depends on a local shared component. That component and its runtime data are not included in this repository.

## 许可 · License

MIT License. · 采用 MIT 许可证。
