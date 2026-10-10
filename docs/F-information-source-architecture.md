# F+G. Information Source & Ingestion Architecture — 信息源与摄取架构

**日期**：2026-10-03 · 依据：research-notes/D（X 合规）、E（新闻财报实测）——所有"实测"均为 2026-10-03 curl 验证

## F. 信息源清单（分层）

### L0 官方结构化层（必装，$0，零噪声，最高可信）

| 源 | 接入 | 实测状态 | 内容 |
|---|---|---|---|
| SEC EDGAR | submissions / companyconcept / full-text search API | ✅ 200（必须带 UA，10 req/s） | filings、8-K 财报事件、XBRL 结构化指标 |
| Federal Reserve | `federalreserve.gov/feeds/press_all.xml` 等 6+ feed | ✅ 200，分钟级 | FOMC 决议、讲话、执行公告 |
| ECB | `ecb.europa.eu/rss/press.html` | ✅ 200 | 欧央行新闻稿/讲话 |
| Bank of Japan | `boj.or.jp/en/mopo/mpmdeci/mpr_2026/` HTML | ✅ 200（无 RSS，需轻解析） | 日银政策声明（年约 8 次） |
| US Treasury | fiscaldata API | ✅ 200（官方 RSS 已 404） | 美债收益率曲线、财政数据 |
| FRED | API（免费 key） | ✅ | DGS2/10、T10Y2Y、DFF、CPI 等 |
| ECB SDMX / BoE CSV / DBnomics(BoJ) / IMF / World Bank / OECD | REST/CSV | ✅ | 各央行宏观（全部无 key） |
| Nasdaq earnings calendar | `api.nasdaq.com/api/calendar/earnings` | ✅ 200（需浏览器 UA） | 财报日历 + 一致预期 |

### L1 免费新闻 RSS 层（默认主力）

| 源 | 实测 URL | 状态 | 用途/降权说明 |
|---|---|---|---|
| CNBC 多频道 | `search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=…` | ✅ 分钟级 | 快讯主力 |
| MarketWatch/WSJ | `feeds.content.dowjones.io/public/rss/mw_topstories` 等 | ✅ | 深度标题+摘要 |
| Yahoo ticker feed | `feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL` | ✅ | **按持仓定制**；避免综合 feed（第三方农场内容，降权） |
| Google News RSS | `news.google.com/rss/search?q=…` | ✅ | Reuters/Bloomberg/FT 的合规兜底（Reuters 官方 RSS 已死） |
| Bloomberg/FT/Economist | 各自 rss | ✅ 标题+摘要 | paywall：只存摘要+链接 |
| Seeking Alpha 快讯 | `seekingalpha.com/market_currents.xml` | ✅ | 快讯免费；深度文付费墙 |
| ZeroHedge | feedburner 全文 feed | ✅ | 可信度标注为 Low，仅情绪参考 |
| Substack/newsletter | `[name].substack.com/feed` | ✅ | **X 层的免费替代**：金融 KOL 深度内容 |
| 机构研究（BlackRock/JPM/GS/Vanguard） | 官网页面 | ✅ 无 RSS | 每周 diff 抓取，摘要+链接（版权边界见 research-notes/E §4） |
| Motley Fool transcripts | `fool.com/earnings-call-transcripts/` | ✅ 200 | 电话会全文（免费） |

### L2 X 情报层（可选付费插件，默认关闭）

- 唯一合规路径：**X API PPU**（$0.005/条，List timeline 一次请求覆盖 N 账号，24h 去重计费），BYOK。
- 灰色路径（Nitter 已死 / RSSHub 需登录 cookie / Apify / SocialData）**全部不做**。
- 合规边界：本地存储+自用展示 ✅；对外再分发全文 ❌；摘要+原链接 ⚠️偏安全。
- 成本：20 KOL × 10 推/天 ≈ $30/月；RSS/Newsletter 兜底 $0。

## G. 摄取管线

### G1. Collect → Filter → Understand → Verify → Relate → Analyze → Personalize → Notify（用户第四节的八步）

```
[Collect]  scheduler(每5-15min) → fetcher(RSS/JSON/HTML per source) → raw/ 落盘
     ↓
[Filter]   去重三级键: canonical_url → 标题simhash(0.9)+24h窗 → 事件键(ticker,event_type,period)
           语言/币种/地区粗筛 + 黑名单(广告/软文 host)
     ↓
[Understand] 小模型批量: 摘要(2句) + 实体抽取(ticker/央行/货币/指标) + 分类(event_type)
             + 五类标签预判(Fact/Expectation/Analysis/Opinion/Signal)
     ↓
[Verify]   声称含事实/预期 → 证据链查询: EDGAR full-text / Fed RSS / 央行发布 / 权威媒体交叉
           → reliability: Primary(官方原文)/High(权威媒体)/Medium/Low/Unverified
     ↓
[Relate]   Source Graph join: 实体→edge→我的敞口（例: BoJ→JPY→我的JPY现金/日股ETF）
           → relevance_score = f(敞口权重, 事件罕见度, 时效)
     ↓
[Analyze]  Portfolio Analyst / Opportunity Agent 消费（见 E 报告）
     ↓
[Personalize] Personal CFO 合成 Daily Brief："今天值得你知道的 3-5 件事"+"与你有关的一件事"
     ↓
[Notify]   本地 UI 通知 /（可选）Telegram Bot 推送 / 邮件摘要
```

### G2. 调度表（频率与成本对齐实测更新节奏）

| 任务 | 频率 | 备注 |
|---|---|---|
| 高频 RSS（CNBC/SA/GNews） | 10-15 min | CNBC ttl=60 |
| ticker RSS（持仓） | 30 min | |
| 央行 RSS（Fed/ECB） | 30 min；FOMC 日 5 min | 事件稀疏 |
| EDGAR submissions（持仓 CIK） | 1 h | 10 req/s 上限内 |
| 行情日线批量 | 每日收盘后 1 次 | yfinance 限流现实 |
| 汇率（frankfurter） | 每日 1 次 | |
| 宏观（FRED 等） | 每日 1 次 | |
| Nasdaq earnings calendar | 每日盘前 1 次 | |
| transcripts/机构页 diff | 每日 1 次扫描 | 低频 |
| X List（若启用） | 30-60 min | since_id 增量，24h 去重 |
| Daily Brief 生成 | 每早 07:00 本地 | data_snapshot_hash 绑定 |

单进程 APScheduler 即可（无需消息队列）；每次 fetch 记 `fetch_log`（成功/失败/耗时/条数），失败指数退避 + 换 provider。

### G3. 存储、去重与 paywall 策略

- 只存 `title + summary(官方RSS description) + url + published_at + source + embedding`；付费墙源不抓正文（FT/WSJ/Economist/SA/Bloomberg）。
- ZeroHedge 等全文 feed 存全文但 `reliability=Low`。
- embedding 用小模型（本地或便宜 API），sqlite-vec 存，Chat RAG 用。
- 原始 payload 保留 90 天（`raw/` 按日分目录），供重放与审计。

### G4. 事件模型（把"新闻"升维成"事件"）

新闻条目是易变的皮，`events` 表才是资产：

```
event: {type: rate_decision, entity: BOJ, occurred_at, payload:{rate:+0.25, from:0.5,to:0.75},
        evidence:[boj-official-url, reuters-url], reliability: Primary}
```

- 同一事件的多篇报道通过事件键归并（"NKE FY2027Q1 earnings"一篇 CNBC + 一篇 SA + 一条 X signal → 一个 event，三条 item）。
- **Portfolio-Aware News 的实现基础**：event.entity 与 Source Graph 边连到我的账户 → `relevance = Σ(edge_weight × exposure_pct)`。例：BoJ 加息事件 → `JPY现金(HKD敞口)` edge 0.9 × 15% + `日本ETF` edge 0.8 × 10% → relevance 0.215 → 进 brief 的"与你有关"区并生成用户第十节格式的解释（What happened/Why it matters/Your exposure/Possible implications/What to watch）。
