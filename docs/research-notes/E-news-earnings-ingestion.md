# 个人 AI 财富管理工具：新闻 / 财报 / 机构研报机器可读摄取渠道调研报告

**调研日期：2026-10-03。除标注外，所有"实测"均为当日 curl GET 结果（状态码 + 内容取样）。**

## 0. TL;DR

| 层级 | 结论 |
|---|---|
| 免费新闻 RSS | CNBC / Google News / Seeking Alpha 快讯 / MarketWatch / Bloomberg / FT / WSJ / Economist / ZeroHedge **全部实测可用**且内容新鲜 |
| 已死/受限 | Reuters 官方 RSS（DNS 已不解析）；Treasury 官方 RSS（404）；SEC XBRL frames API（实测 404）；Morningstar RSS（403） |
| 官方 API | Fed RSS 完整、ECB RSS 可用、SEC EDGAR（submissions/companyfacts/companyconcept/full-text search）全部 200，是财报数据的最优免费来源 |
| 财报 | EDGAR XBRL（结构化指标，免费）+ Motley Fool transcripts（免费全文）+ Nasdaq earnings calendar（免费 JSON）可组成完整免费链路 |
| 机构研究 | Vanguard/BlackRock/JPM/GS 页面均公开可读，但**均无 RSS**，需页面监控 + newsletter |

---

## 1. 新闻 RSS 可用性实测

### 1.1 金融媒体（核心源）

| 源 | 实测 URL | 状态 | 内容形式与备注 |
|---|---|---|---|
| CNBC Top News | `https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114` | 200 / 20KB | item 含 title+description 摘要，`ttl=60`，实测最新条目 2026-10-03 15:00 GMT（分钟级新鲜）。频道 id 可换：20910258（Markets）实测 200 |
| MarketWatch | `https://feeds.content.dowjones.io/public/rss/mw_topstories` | 200 / 8KB | 标题+摘要，实测最新 2026-10-03 15:06 GMT。注意旧地址 `www.marketwatch.com/rss/topstories` 已 301 |
| WSJ World News | `https://feeds.content.dowjones.io/public/rss/RSSWorldNews` | 200 / 50KB | 同一 Dow Jones feed 基础设施，稳定；旧 `wsj.com/xml/rss/3_7031.xml` 已 301 到 RSS 目录页 |
| Yahoo Finance 综合 | `https://finance.yahoo.com/news/rssindex` | 200 / 29KB | **质量下降**：大量第三方农场内容（Insider Monkey/247wallst 等），混有 2024-2025 旧文，channel 更新约滞后数天 |
| Yahoo Finance 按 ticker | `https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL&region=US&lang=en-US` | 200 / 12KB | 实测最新 2026-10-02 23:03 UTC，按符号定制，新鲜度好于综合 feed，**推荐用这个** |
| Google News RSS | `https://news.google.com/rss/search?q=<query>&hl=en-US&gl=US&ceid=US:en` | 200 / 133KB | 按任意 query 定制，item 含来源名与发布时间，实测新鲜。**是 Reuters/Bloomberg 细分主题的最佳兜底** |
| Investing.com | `https://www.investing.com/rss/news.rss`、`/rss/news_285.rss` 等 | 200 / 4.9KB、3.4KB | 标题+摘要，实测最新 2026-10-03 15:18；内容偏杂（含黑客/币圈），仅作补充 |
| Seeking Alpha 快讯 | `https://seekingalpha.com/market_currents.xml` | 200 / 9.4KB | Market Currents 快讯流，实测最新 2026-10-03 11:24 EDT，免费可用 |
| Seeking Alpha 分析 | `https://seekingalpha.com/feed.xml` | 200 / 31KB | 分析文章标题+摘要；正文有硬付费墙（非订阅者全文隐藏），快讯类免费、深度分析付费 |

### 1.2 通讯社与付费墙媒体

| 源 | 实测结果 | 处理建议 |
|---|---|---|
| Reuters | `feeds.reuters.com/reuters/topNews` → **连接失败（HTTP 000，域名不解析）**。官方 RSS 于 2020 年 6 月关闭，至今未恢复 | 用 Google News RSS `q=reuters.com` 或按主题 query 间接覆盖；Yahoo ticker feed 也转载 Reuters（实测样本含 reuters.com 来源条目） |
| Bloomberg | `feeds.bloomberg.com/markets/news.rss` 301 → `https://www.bloomberg.com/feeds/markets/news.rss` → **200 / 17KB**，实测最新 2026-10-03 15:25 GMT | RSS 给标题+摘要；正文付费墙。摘要+外链模式可用 |
| FT | `https://www.ft.com/rss/home` 301 → `/rss/home/international` → **200 / 7KB**，实测最新 2026-10-03 08:01 GMT | 同上，标题+摘要可用，全文付费 |
| The Economist | `https://www.economist.com/finance-and-economics/rss.xml` → **200 / 150KB**，item 含 description，实测最新 2026-10-02；根路径 `/rss.xml` 已 404 | 分栏目 feed 给标题+摘要，足够做选题/摘要；全文付费 |
| ZeroHedge | `https://feeds.feedburner.com/zerohedge/feed` → **200 / 217KB，全文 feed**，实测最新 2026-10-03 14:30 UTC；站内 `/fullrss2.xml` 已 404 | 少见的全文 RSS；内容立场需在摘要层做可信度标注 |
| FRED Blog | `https://fredblog.stlouisfed.org/feed/` → 200 / 45KB | WordPress 标准 feed，可用 |

**付费墙结论**：Bloomberg/FT/Economist/WSJ 的 RSS 均提供 title + 1-3 句摘要，对"AI 摘要 + 原文链接"的个人工具模式完全够用；抓全文既违反 ToS 也不稳定。

---

## 2. 官方来源机器可读性

### 2.1 Federal Reserve — 最完善

- **RSS 目录页**：`https://www.federalreserve.gov/feeds/feeds.htm`（200）。可用频道（实测列出）：`press_all.xml`、`press_monetary.xml`、`press_enforcement.xml`、`speeches.xml`、`testimony.xml`、`speeches_and_testimony.xml`，以及每位理事单独 feed（如 `s_t_powell.xml`、`s_t_waller.xml`）。
- **实测** `https://www.federalreserve.gov/feeds/press_all.xml` → 200，最新条目 2026-10-02 20:45 GMT，item 含标题+链接+日期（正文在链接页，HTML 干净）。
- **FOMC 日历**：`https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm` → 200，静态 HTML，可解析会议日期；无 JSON API，但结构多年稳定。
- 无官方 JSON press API；RSS + HTML 足够。

### 2.2 ECB

- `https://www.ecb.europa.eu/rss/press.html` → **200**，覆盖 press releases/speeches/interviews，实测最新 2026-10-02。item 只有标题+链接+日期（无摘要），链接直达 `.html` 或 `.pdf` 全文（全文免费）。够用。

### 2.3 Bank of Japan

- `https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/index.htm` → **200**，"Monetary Policy Releases 2026" 静态 HTML 列表页（无 RSS）。政策声明为 PDF/HTML 双格式，需轻量页面解析；更新频率低（每年约 8 次），日级轮询即可。

### 2.4 SEC EDGAR — 财报数据基石（全部实测 200）

| 端点 | 实测 URL（AAPL, CIK 0000320193） | 结果 |
|---|---|---|
| Submissions | `https://data.sec.gov/submissions/CIK0000320193.json` | 200 / 164KB，含全部近期 filing 元数据 |
| Company Facts | `https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json` | 200 / **3.8MB**，全量 XBRL 事实 |
| Company Concept (EPS) | `https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/EarningsPerShareDiluted.json` | 200 / 48KB，含逐期值+form+filed |
| Company Concept (Revenue) | `.../us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax.json` | 200 / 18KB |
| Full-text Search | `https://efts.sec.gov/LATEST/search-index?q=%22earnings%22&forms=8-K` | 200，Elasticsearch 风格 JSON，`forms=` 过滤可用 |
| XBRL Frames | `https://data.sec.gov/api/xbrl/frames/US-GAAP/Assets/USD/CY2020Q1.json`（官方文档示例） | **404 NoSuchKey**（大小写、2020/2023/2024 多组合均 404）。官方文档仍列出该 API，但实测不可用 → **用 companyconcept/companyfacts 替代** |

- **政策**：必须自定义 `User-Agent`（如 `SampleCo AdminContact@sample.com`），限速 10 req/s；批量抓取需声明用途。实测无 UA 也能通，但为合规必须带。

### 2.5 US Treasury

- **官方 RSS 已失效**：`home.treasury.gov/news/press-releases/feed` 及多个变体均 404（未见官方关停公告，疑为 CMS 改版后移除）。
- **FiscalData API 实测正常**：`https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates?page[size]=1` → 200 JSON（分页/过滤完善，文档佳）。债务数据表 `debt/sec_mts_monthly` 路径已变（404），以 fiscaldata.treasury.gov 数据目录为准。
- 新闻类替代：Google News RSS `q=site:home.treasury.gov` 或官方邮件订阅。

---

## 3. 财报（Earnings）摄取

### 3.1 结构化指标（免费最优解：EDGAR XBRL）

- 8-K（earnings release）+ 10-K/10-Q（完整报表）通过 submissions JSON 发现 accession number，再用 companyconcept 拉 `Revenues` / `EarningsPerShareDiluted` / `NetIncomeLoss` / `GrossProfit`（margin 自算）。实测 AAPL 单概念 JSON 18-48KB，结构干净（`val`/`start`/`end`/`form`/`filed`），**完全可行**。
- 注意：公司间 tag 有差异（有的用 `Revenues`，有的用 `RevenueFromContractWithCustomerExcludingAssessedTax`），需按公司做 tag 回退列表。

### 3.2 电话会 Transcript

| 源 | 实测 | 评价 |
|---|---|---|
| Motley Fool | `https://www.fool.com/earnings-call-transcripts/` → 200 / 382KB，可解析出 `/earnings/call-transcripts/2026/10/02/nike-nke-q1-2027-...` 等**当日**链接 | **免费全文首选**，延迟数小时-1天，HTML 结构稳定 |
| Seeking Alpha | transcripts 需登录（RSS 层面同上） | 付费墙，不作为机器源 |
| Stock Analysis | `stockanalysis.com/stocks/aapl/`、`/financials/` → 200，但 `stockanalysis.com/api/...` → 403（Cloudflare）、`api.stockanalysis.com` → 404 | 页面可读但**无开放 API**，只能 HTML 解析，稳定性一般 |
| FMP | `financialmodelingprep.com/api/v3/earning_calendar?apikey=demo` → 401（Invalid API KEY） | 有免费层（需注册），transcript/earnings API 齐全，适合作为**付费升级项** |

### 3.3 Earnings Calendar

- **Nasdaq（免费，实测 200）**：`https://api.nasdaq.com/api/calendar/earnings?date=2026-10-06` → JSON，含 EPS 一致预期、去年 EPS、报告时间（盘前/盘后）。需带浏览器 UA。
- **Finnhub**：`finnhub.io/api/v1/calendar/earnings` → 401（需免费 API key）。
- **FMP**：同上 401，免费层可用。
- 建议：Nasdaq 免费 API 做日历，EDGAR 8-K 做实际确认。

---

## 4. 机构研究公开层

| 机构 | 入口（实测） | 机器可读性 | 摘要+链接可行性 |
|---|---|---|---|
| BlackRock Investment Institute | `https://www.blackrock.com/us/individual/insights/blackrock-investment-institute/weekly-commentary` → 200 / 162KB | 无 RSS；有 newsletter 订阅 | Weekly Commentary 全文公开，摘要+链接 OK |
| JPMorgan Insights | `https://www.jpmorgan.com/insights` → 200 / 206KB | 无 RSS；页面为 JS 渲染为主 | 文章公开可读；摘要+链接 OK |
| Goldman Sachs Insights | `https://www.goldmansachs.com/insights/` → 200 / 1.1MB | 无 RSS；HTML 内嵌数据较多 | 公开文章可读 |
| Morningstar | `https://www.morningstar.com/markets` → 200；`/articles` → 404（栏目调整）；`/rss` → 403 | 无公开 RSS | 部分文章免费、部分付费标记；反爬较强 |
| Vanguard (VEMO) | 老 `vanguard.com/economicmarketoutlook` 与 `corporate.vanguard.com/economic-market-outlook.html` 均 404；现行路径为 `corporate.vanguard.com/content/corporatesite/us/en/corp/vemo/` 系列页 + 年度 PDF（research 目录） | 无 RSS | 年度/季度 outlook 公开 PDF 可摘要 |

**版权边界（个人工具）**：标题+官方摘要（RSS description）+原文链接+出处标注，属于通行做法、风险低；不应全文入库再展示、不应批量再分发机构 PDF 内容；LLM 生成的二次摘要需标注"基于 X 机构公开摘要"。

---

## 5. 汇总：新闻摄取管线推荐

### 5.1 分层优先级

1. **L0 官方结构化（最高优先，免费）**：SEC EDGAR（submissions/companyconcept/full-text search）→ Fed press_all + monetary RSS → ECB press RSS → fiscaldata API。真实事件（filing/决议）从这里来，噪声为零。
2. **L1 免费 RSS 新闻层**：CNBC（多频道）+ Seeking Alpha market_currents + MarketWatch/Dow Jones feed + Yahoo ticker feed（按持仓定制）+ Google News RSS（按主题 query 补 Reuters/Bloomberg/FT/Economist 覆盖）+ ZeroHedge/FRED blog（可选）。
3. **L2 页面解析层（低频）**：Motley Fool transcripts 列表页、Nasdaq earnings calendar、BOJ statements 页、机构 insight 页（weekly diff）。
4. **L3 付费升级（按需）**：FMP/Finnhub（transcript+calendar+estimates 一体化）、Seeking Alpha Premium（深度分析全文）、Bloomberg/FT 订阅（仅当需要原文）。

### 5.2 抓取频率建议

| 源类型 | 频率 | 依据 |
|---|---|---|
| 高频新闻 RSS（CNBC/SA/GNews） | 5-15 min | CNBC 自标 `ttl=60`；实测分钟级更新 |
| ticker 级 RSS | 15-30 min | Yahoo ticker feed 实测小时级 |
| 央行 RSS（Fed/ECB） | 15-30 min（FOMC 日提高至 5 min） | 事件稀疏，成本极低 |
| EDGAR submissions | 每小时（持仓股 10 只内可 15 min，注意 10 req/s 上限） | filing 时效要求小时级即可 |
| earnings calendar（Nasdaq） | 每日盘前 | 日粒度数据 |
| transcripts / 机构页 | 每日或每周 diff | 更新低频 |

### 5.3 去重与 paywall 策略

- **去重三级键**：① canonical URL（去 utm/query 参数、Google News 重定向需解析原链接）；② 标题 simhash（0.9 阈值）+ 24h 时间窗；③ 事件级键 `(ticker, event_type, period)`（如 `(NKE, earnings, FY2027Q1)`），多源报道归并到同一事件对象。
- **Paywall 处理**：只存 `title + RSS description + pubDate + canonical_url + source`，全文付费源（FT/Economist/WSJ/SA/Bloomberg）不抓正文；AI 摼要基于官方 description 生成并在 UI 明示"完整内容请访问原文"；ZeroHedge 等全文 feed 可存全文但需标注可信度分层。
- **源质量标注**：Yahoo 综合 feed 的第三方农场内容（Insider Monkey 等）建议降权或只取 ticker feed；Reuters 内容通过 Yahoo/Google News 间接收敛并保留原始 source 字段。

### 5.4 已确认不可用清单（避免踩坑）

- `feeds.reuters.com/*`（DNS 失效）、`www.marketwatch.com/rss/*`（301）、`wsj.com/xml/rss/*`（301）、`economist.com/rss.xml`（404）、`zerohedge.com/fullrss2.xml`（404）
- `home.treasury.gov` 全部 RSS 变体（404）
- SEC XBRL **frames** API（实测 404，含官方文档示例参数；用 companyconcept 替代）
- `stockanalysis.com/api/*`（403/404）、`morningstar.com/rss`（403）、`finance.yahoo.com/news/rssindex` 的第三方内容质量

---

**主要参考来源**：
- [SEC EDGAR API 官方文档](https://www.sec.gov/developer)
- [Seeking Alpha 官方 Feeds 页](https://about.seekingalpha.com/feeds)
- [Fed RSS 目录](https://www.federalreserve.gov/feeds/feeds.htm)
- [FiscalData Treasury API](https://fiscaldata.treasury.gov/)
- [EdgarScout EDGAR API 指南](https://edgarscout.com/edgar-api)（frames 404 常见原因）
- [BlackRock Investment Institute Weekly Commentary](https://www.blackrock.com/us/individual/insights/blackrock-investment-institute/weekly-commentary)
- [JPMorgan Insights](https://www.jpmorgan.com/insights)、[Goldman Sachs Insights](https://www.goldmansachs.com/insights/)
