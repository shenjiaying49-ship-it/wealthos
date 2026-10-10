# 行情与宏观数据源调研报告（2026-10-03）

**目标场景**：本地优先（SQLite）个人 AI 财富管理工具，单用户，日频 + 盘中分钟级，覆盖美股/港股/日股/ETF/外汇/利率/加密货币。
**调研方式**：逐项核对官方定价页/API 文档 + 2025–2026 社区报告交叉验证。

---

## 一、主对比表

| 数据源 | 类别 | 免费额度（2026 核实） | 无需 key? | License / ToS 风险 | 覆盖范围 | 2026 可用性 |
|---|---|---|---|---|---|---|
| **yfinance** (Yahoo) | 股票/ETF/FX/加密/指数，日线+盘中 | 无配额，但 IP 级 429 限流（几十次请求即可触发） | ✅ | **灰色**：Yahoo ToS 禁止自动化抓取；README 自述仅"研究与教育用途"、非官方授权 | US/HK(.HK)/JP(.T)/EU/加密(=USD对)/FX(=X) | ⚠️ 可用但脆弱：靠 curl_cffi 模拟 Chrome 指纹，cookie/crumb 端点经常变 |
| **Stooq** | 股票/ETF/指数/FX/商品，日频为主（部分 5min/小时） | 完全免费 CSV + 全市场打包下载（US/JP 220MB/HK 105MB/DE 等） | ✅ | 个人使用免费；商业/再分发需联系授权；实测服务器 IP 偶触发 JS 人机验证，需低频+UA | US/HK（含港股、HSI、HK ETF）/JP（含 Nikkei225、JP ETF）/EU/FX | ✅ 稳定，运行多年，是 yfinance 倒下后的社区标配兜底 |
| **Alpha Vantage** | 股票/FX/加密，日线+基本面 | **25 请求/天**（早年 500/天已缩水）；付费 $49.99/月起 | ❌ | 低：官方 API、条款清晰 | US/全球部分、FX、加密 | ✅ 可用，但 25/天 对多资产组合太紧 |
| **Finnhub** | 报价/财报日历/基本面 | 60 请求/分钟；**美股 `/stock/candle` 不在免费档**（2025-04 官方 GitHub 确认） | ❌ | 低；部分 calendar/economic 端点正逐步转 premium | US 为主 + 部分国际、FX、加密 | ✅ 可用；免费档定位为"实时报价+辅助端点" |
| **Twelve Data** | 股票/ETF/FX/加密，实时+历史 | **8 credits/分钟、800/天**，含实时美股/ETF/FX/加密、技术指标、批量请求 | ❌ | 低 | US + 3 个市场类别（免费档）；付费扩展全球 | ✅ 可用，免费档在"正规 API"里最宽裕 |
| **EODHD** | EOD/延迟报价/宏观/美债 | **Sandbox 免费：20 次/天**（+500 注册赠送）；1 年全球 EOD 历史、15 分钟延迟报价、美债收益率、商品 | ❌ | 低；免费档仅供测试 | 全球股票/ETF/FX/加密/指数 | ✅ 可用；付费 EOD 档 $19.99/月（30 年历史、10 万次/天）性价比高 |
| **FMP** | 基本面/EOD/财报日历 | **250 请求/天**；EOD 历史+Profile+参考数据；150+ 端点中可用子集 | ❌ | 低 | 免费档 US 为主；付费 $19/月起扩全球/FX/加密 | ✅ 可用；deep fundamentals 与 calendars 多在 $49/月档 |
| **Tiingo** | EOD/IEX 实时/加密 | **$0 Starter：500 只代码/月、50 次/小时、1000 次/天**、30+ 年历史 | ❌ | 低；**Internal use only**（不可再分发） | 美股+中概、ETF/共同基金、加密；IEX 实时 | ✅ 可用，历史深度极长（30 年+） |
| **Polygon.io → Massive** | 美股分钟级/EOD | 免费：**5 请求/分钟**、US 全市场、EOD + **2 年历史 + 分钟级 aggregates**，仅个人使用 | ❌ | 低；明确"Individual use" | 仅美股（免费档）；FX/期权/指数在付费档 | ✅ 可用；**2025-10-30 已改名 Massive**（massive.com），旧 key/端点不变 |
| **frankfurter** | 汇率（ECB 系） | 完全免费、无配额、限速宽松；223 币种、1948 年至今、104 家央行/官方来源 | ✅ | 极低：开源可自托管（Docker），数据权利归各来源 | 主要货币对日频中间价 | ✅ 2026 大升级版（frankfurter.dev），本地优先首选 |
| **exchangerate.host** | 汇率 | 需 APILayer key，免费约 100 次/月 | ❌（2023 起强制 key） | 低 | 168 币种 | ⚠️ 可用但免费额度几乎无意义，已被 frankfurter 取代 |
| **FRED** | 美国宏观/利率/国债收益率 | 免费 key，无公开硬配额（社区实践 ≤120 次/分钟安全） | ❌（免费注册 key） | 极低：圣路易斯联储官方，宽松 | 美国 + 部分国际系列（含部分 BoJ/日韩数据） | ✅ 非常稳定 |
| **US Treasury (fiscaldata.gov)** | 美债收益率/财政 | 无 key 30 次/分钟；免费 key 1000 次/小时 | ✅ | 极低：美国政府公共领域 | 美债 par yield curve 全期限日频 | ✅ 稳定；旧版 home.treasury.gov CSV/XML 直链仍有效 |
| **ECB Data Portal** | 欧元区宏观/政策利率/FX/收益率曲线 | 免费、无 key，SDMX 2.1 REST，SDMX-JSON/CSV/XML | ✅ | 极低：官方 | 欧元区 + 欧元参考汇率 30+ 币种 | ✅ 稳定（data-api.ecb.europa.eu） |
| **日本银行 (BoJ)** | 日本宏观/利率 | **无官方公开 REST API**；时系列统计检索可下载 CSV | ✅（CSV） | 低 | 日本货币/利率/国际收支 | ⚠️ 程序化访问建议走 **DBnomics API**（免费 JSON，镜像 BoJ 系列）或 FRED |
| **Bank of England (BMD/IADB)** | 英国利率/汇率/市场 | 免费，按序列码 CSV 下载（boeapps/iadb 端点） | ✅ | 低：官方开放数据 | UK Bank Rate、SONIA、金边债券收益率、FX | ✅ 可用；无正式 REST API 但 CSV URL 模式稳定，有成熟 Python/R 封装 |
| **IMF DataMapper** | 全球宏观（WEO 等） | v2 API 免费，JSON | ✅ | 低 | 全球各国宏观指标 | ✅ 可用（imf.org/external/datamapper/api/v2） |
| **World Bank API v2** | 发展宏观指标 | 免费，JSON/XML/JSON-stat/CSV/EXCEL，≤60 指标/次 | ✅ | 低 | 全球 | ✅ 稳定（api.worldbank.org/V2） |
| **OECD SDMX** | 成员国宏观 | 免费、无 key，sdmx.oecd.org，SDMX-JSON/CSV/ML | ✅ | 低 | 38 国+伙伴国 | ✅ 可用 |
| **CoinGecko** | 加密货币 | **Demo 免费档：30 次/分钟、10,000 次/月**（需注册 key）；下一档直接 $129/月 | ❌（免费注册） | 低：需署名/遵守条款 | 全加密市场 | ✅ 可用；旧的完全无 key 公共端点已收编进 demo key 体系 |
| **HKEX 官方** | 港股行情 | **无免费官方行情 API**；实时数据须走授权供应商；2024-12 上线 Data Marketplace（历史/每日参考数据，付费） | — | 高成本 | 港股 | ❌ 免费档不存在；官网仅有延迟报价与每日收盘下载 |
| **SEC EDGAR (data.sec.gov)** | 美股财报/基本面 | 完全免费：submissions JSON、XBRL companyfacts/frames | ✅ | 极低：仅需带联系方式的自定义 User-Agent + ≤10 请求/秒 | US 上市公司 | ✅ 稳定，官方开放 |

---

## 二、分类要点详注

### 1. 股票/ETF：yfinance 的真实处境
- 2025–2026 年 Yahoo 未"全面封锁"，但**风险显著上升**：限流是 IP 级且不宽容（实测一次 dashboard 会话约 78 个请求即被拦）；报错常被误标为 "Too Many Requests"，实际是客户端指纹识别，yfinance 靠 curl_cffi 伪装 Chrome TLS + cookie/crumb 握手维持可用，Yahoo 一改端点就需紧急升级库版本。
- ToS 层面：yfinance README 明确声明与 Yahoo 无关联、仅供研究教育用途，数据权利受 Yahoo 服务条款约束——**个人本地工具属低风险灰区，但不要用于商业产品或高并发**。
- 实操建议：低频（每日收盘后批量一次）、本地缓存、`yf.download()` 合并代码、绝不并发；同时实现 Stooq 兜底。

### 2. 汇率
- **frankfurter 是最优解**：无 key、无配额、开源可 Docker 自托管进本地架构（彻底"本地优先"），2026 版从"纯 ECB"扩展为 104 个官方来源混合，历史可回溯到 1948。
- exchangerate.host 已商业化为 APILayer 服务（免费 ~100 次/月），不再推荐。
- ECB 官方 SDMX（`data-api.ecb.europa.eu`）可作为欧元参考汇率的权威备选。

### 3. 利率与美债
- FRED（免费 key）拿 `DGS10/DGS2/T10Y2Y/DFF` 等即可覆盖绝大多数需求；
- 权威兜底用 fiscaldata.gov 的 `daily_treasury_par_yield_curve_rates`（无需 key），每天一次调用远低于限制。

### 4. 央行/官方宏观（全部免费、除 BoJ 外均无 key）
- Fed：FRED + FOMC 声明页面（无官方 JSON，可用 FRED 的政策利率系列代替）。
- ECB / IMF / World Bank / OECD：均为**无 key 开放 API**，SDMX 或 JSON，稳定且可长期依赖。
- BoJ 是唯一短板：无官方 API，方案 = CSV 手动/半自动下载，或 **DBnomics**（免费 JSON API，含 2700+ BoJ 系列），或 FRED 收录的日本系列。
- BoE：IADB/BMD 的 CSV 端点虽非正式 REST API 但多年稳定，社区有现成封装。

### 5. 加密货币
- CoinGecko 免费 Demo 档（30/min、10k/月）对个人日频完全够用；付费跳档太陡（$129/月），超出本工具预算模型。备选：yfinance 的 `-USD` 交易对（同灰区）。

### 6. 港股/日股
- **免费组合即可覆盖**：Yahoo（0700.HK / 7203.T）+ Stooq（HK 全库 105MB、JP 全库 220MB 打包日频下载，含 Nikkei225 成分与 HK ETF 列表）。
- HKEX 没有免费官方行情 API；实时行情须付授权费，Data Marketplace 是付费历史数据商店。免费档无需考虑官方渠道。

### 7. 财报日历与基本面
- **EDGAR 是零成本基本面的主力**（submissions + companyfacts + frames，10 req/s 上限，务必设含邮箱的 User-Agent）。
- Finnhub earnings calendar（`/calendar/earnings`）历史上在免费档，但该司有把 calendar/economic 端点 premium 化的趋势——代码里应处理响应中的 `premium` 标志做降级。
- FMP 免费档（250 次/天）可用 Profile/参考数据；完整财报日历与深度基本面在 $19–49/月档。

---

## 三、推荐组合

### MVP：零成本方案（全免费，月支出 $0）
| 类别 | 首选 | 兜底 |
|---|---|---|
| 美股/ETF 日线+盘中 | **yfinance**（低频+缓存） | **Stooq CSV** / Polygon(Massive) 免费 5/min（US 2 年分钟线） |
| 港股/日股 日线 | **Stooq**（打包全库，定期增量） | **yfinance**（.HK/.T 后缀） |
| 实时报价快照 | **Twelve Data 免费**（800/天）或 Finnhub（60/min，非 K 线端点） | yfinance |
| 外汇 | **frankfurter**（无 key 可自托管） | ECB SDMX / Yahoo FX |
| 利率/美债 | **FRED**（免费 key） | **US Treasury fiscaldata**（无 key） |
| 宏观（欧/英/日/全球） | **ECB SDMX + BoE CSV + DBnomics(BoJ) + IMF/WB/OECD** | FRED 收录的国际系列 |
| 加密货币 | **CoinGecko Demo**（10k 次/月） | yfinance `-USD` 对 |
| 基本面/财报 | **SEC EDGAR**（companyfacts） | Finnhub earnings calendar（注意 premium 降级） |

**架构注意**：所有源统一进 SQLite 的 `price_daily` / `fx_daily` / `macro_series` 表，抓取层用"每日定时批量 + 指数退避 + 本地缓存"，yfinance 与 Stooq 互为故障转移。

### 进阶方案：每月 < $30
- **方案 A（推荐）：EODHD EOD Historical $19.99/月** —— 30 年全球 EOD（US/HK/JP/EU/ETF/FX/加密/指数一体解决）+ 10 万次/天，免费 yfinance/Stooq 继续负责盘中分钟级。最省心的"日频正规化"路线。
- **方案 B：FMP Starter $19/月** —— 300 次/分钟、5 年历史、US+加密+外汇+新闻，适合想顺带增强基本面的场景（港股日股覆盖仍靠 Stooq）。
- **方案 C：Tiingo $30/月** —— 1 万次/小时、30+ 年历史、IEX 实时，适合美股为核心、要求历史深度的用户。
- 分钟级数据若要"正规来源"，Polygon/Massive 免费档（US 2 年分钟 aggregates、5 次/分钟）已是 $0 预算内的最佳选项；全市场无限制分钟级需 $29–199/月，超出本预算，对个人日频+盘中快照场景非必需。

### 各类别最终首选+备选速查
- 美股/ETF：**yfinance** → Stooq → EODHD($20)
- 港股：**Stooq** → yfinance → EODHD($20)；官方 HKEX ❌ 无免费 API
- 日股：**Stooq** → yfinance（.T）→ EODHD($20)
- 外汇：**frankfurter** → ECB SDMX
- 利率/美债：**FRED** → fiscaldata.gov
- 央行宏观：**ECB SDMX** / BoE CSV / **DBnomics(替代 BoJ API)** / IMF DataMapper / World Bank v2 / OECD SDMX
- 加密货币：**CoinGecko Demo**
- 基本面/财报日历：**SEC EDGAR** → Finnhub / FMP($19+)

---

## 四、主要来源

- yfinance 状态与 ToS：[yfinance GitHub README](https://github.com/ranaroussi/yfinance)、curl_cffi 指纹机制（Qiita 2026-08 报告）
- 各源定价（官方页）：[Twelve Data](https://twelvedata.com/pricing)、[EODHD](https://eodhd.com/pricing)、[FMP](https://site.financialmodelingprep.com/developer/docs/pricing)、[Tiingo](https://www.tiingo.com/about/pricing)、[Massive（原 Polygon）](https://massive.com/pricing)、[CoinGecko API 定价](https://www.coingecko.com/en/api/pricing)
- Finnhub 免费档无美股 K 线：GitHub Issue #546（2025-04）
- Polygon→Massive 改名（2025-10-30，key/端点不变）
- Stooq 覆盖（JP 220MB / HK 105MB 打包、Nikkei225/HK ETF 列表）：[stooq.com](https://stooq.com)
- frankfurter 2026 版（223 币种/104 来源/可自托管）：[frankfurter.dev](https://frankfurter.dev/)
- FRED key 与使用条款：[fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html)
- US Treasury API：[fiscaldata.treasury.gov](https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/daily_treasury_par_yield_curve_rates)
- ECB SDMX：[data.ecb.europa.eu](https://data.ecb.europa.eu)（data-api.ecb.europa.eu，无 key）
- BoJ 无官方 API、DBnomics 替代：[boj.or.jp](https://www.boj.or.jp)、[db.nomics.world](https://db.nomics.world)
- BoE 数据库：[bankofengland.co.uk](https://www.bankofengland.co.uk)
- IMF DataMapper v2：[imf.org/external/datamapper/api](https://www.imf.org/external/datamapper/api/)；World Bank v2：[官方 API 文档](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-structure)；OECD SDMX：[sdmx.oecd.org](https://sdmx.oecd.org)
- HKEX 无免费行情 API、Data Marketplace（2024-12）：[hkex.com.hk](https://www.hkex.com.hk)
- SEC EDGAR 限速与规范：[SEC Developer Resources](https://www.sec.gov/about/developer-resources)
