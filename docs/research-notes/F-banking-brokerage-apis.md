# 个人财富管理工具：银行与券商自动同步 API 调研报告（2026-10）

**场景假设**：个人用户，香港/新加坡/日本/美国多地开户，涉及 USD/HKD/JPY/CNY，需要同步银行余额/交易与券商持仓/资产。

## 0. TL;DR

- **银行侧对个人开发者几乎全军覆没**：GoCardless Bank Account Data（原 Nordigen）2025 年 7 月起停止新注册、免费档实质停摆；Plaid/TrueLayer/Tink/Salt Edge 均为企业向；香港 HKMA Open API 二/三阶段只对签约企业 TSP 开放；日本无 PSD2 式立法，靠银行与聚合商（Money Forward）双边协议，个人无门；新加坡 SGFinDex 同样走机构准入。**唯一可用的个人免费银行 API 是 Enable Banking（仅欧洲）与美国 Plaid 个人档（非官方承诺）**。
- **券商侧反而是突破口**：IBKR Flex Query（token + query id，EOD、免会话维护、免费）是自用拉持仓的最优解；长桥 LongPort OpenAPI（无本地网关、直连云端）、老虎 Tiger OpenAPI（开户入金即免费）、富途 FutuOpenAPI（需本地 OpenD 网关常驻）三家中文券商都可只调用查询类接口实现"事实只读"；美股有 Alpaca（API-first）、Schwab Trader API（个人可申请）；SnapTrade 免费档可聚合 5 个美股/加拿大券商账户。
- **加密**：CCXT 2026 年仍活跃维护（v4.5.x，104 家交易所 REST），配 CoinGecko 免费 Demo 档做估值。

---

## 1. 开放银行聚合（银行余额/交易）

### 1.1 GoCardless Bank Account Data（原 Nordigen）— 已对新用户关闭

| 项目 | 现状 |
|---|---|
| 免费档 | **新注册已于 2025 年 7 月停止**；老用户免费档为 50 银行连接/月、每日最多 4 次刷新，但产品整体进入 sunset |
| 覆盖 | 2,300+ 银行、31 个欧洲国家（UK/EU/EEA），PSD2 AIS |
| 港/日/新/美 | **均不覆盖**（纯欧洲产品） |
| 个人条款 | 原本允许个人自用（Actual Budget、Firefly III 社区大量使用），现新个人用户已无法注册 |

社区确认来源：GitHub OCA/bank-statement-import issue #867（2025-12）；dev.to 文章称 "closed to new onboarding since 2025, free tier sunset"。

### 1.2 Plaid — 美国/北美最优，但无亚太覆盖

- 覆盖：**美国、加拿大、英国、欧洲**，12,000+ 金融机构；**不覆盖香港/日本/新加坡/中国的银行**。
- 个人开发者：历史上自服务档有 **100 个免费 linked item**（够个人把所有账户连完），此后按量计费；现行官网为 pay-as-you-go + Growth 合同制，100 免费 item 属历史政策，**需注册后在 dashboard 确认**。
- Investments 产品：可链接券商/退休账户（投资持仓端点是 Plaid 相对独特的个人可用能力），覆盖以美国券商为主。
- 结论：美国银行 + 美国券商聚合的现实首选；对港日新账户无意义。

### 1.3 TrueLayer / Tink / Salt Edge — 企业向，个人不可用

- **TrueLayer**：免费 sandbox；生产为用量计费 + 销售报价，客户是 Amazon 级企业。UK/EU 为主。
- **Tink**（Visa 旗下）：面向银行/金融科技，无个人档；集成成本第三方估算 $28K–171K。
- **Salt Edge**：全球覆盖名义上较广（含部分亚太银行），但开发者文档面向"为自己的用户构建应用的公司"，定制报价。
- **共同点**：三者"免费"仅限 sandbox，个人均无法用生产环境拉自己的账户。

### 1.4 Enable Banking — GoCardless 之后欧洲个人自用的社区首选

- 免费 restricted mode 允许访问**自己的**银行账户，2,700+ 银行、30 个欧洲国家；Firefly III 数据导入器与 Actual Budget 社区均已接入。
- 仅欧洲；对亚太无帮助。

### 1.5 香港 HKMA Open API 框架 — 个人开发者不可用

- 框架 2018-07 发布，四阶段：Phase 1 产品信息（公开）、Phase 2 账户信息（2019-10 左右部署，众多银行延期）、Phase 3 交易发起、Phase 4 信贷数据。
- 关键限制：Phase 2/3 的账户数据 API 只向**与银行签订商业协议的 TSP（第三方服务供应商）**开放（如中银香港开放 API 条款明确 "提供给 TSP"，需先签约；银行对 TSP 有尽调、信息安全评估、渗透测试要求）。**没有类似欧洲 PSD2 的"个人有权要求银行开放数据"的法定权利**，个人开发者实际无法接入。
- 香港银行的账户数据自动同步，对个人而言只能：CSV/MT940 导出导入，或使用 Peritus、Bowtie 类已签约 TSP 的消费级 App（无 API 给你）。

### 1.6 日本 — 无个人开放 API

- 无综合开放银行立法：基于《银行法》修订的"框架协议 + 注册电子支付服务提供商（资金移动/账户聚合）"模式，靠银行与聚合商逐家谈；监管正推动从抓屏转向正式 API，但进度落后 UK/EU。
- Money Forward ME 是最大的个人聚合 App（数百银行，大量仍靠抓屏），**不对外提供个人 API**。
- 主流网络券商（SBI、乐天、Monex）**均不提供个人股票交易/账户 API**（Monex 曾有 FX API 已终止）。
- 日本账户：CSV 导入是唯一现实路径。

### 1.7 新加坡 — SGFinDex 机构准入

- SGFinDex（2020-12 上线，MAS 主导，Singpass 授权）是官方个人金融数据交换基础设施，但 API 只开放给**经批准的金融机构/合作方**（需 Singpass/MyInfo 集成 + FAPI 2.0 合规），个人开发者无法自服务接入。
- 个人路径 = 使用已接入 SGFinDex 的理财 App，或 CSV 导入。

---

## 2. 券商同步与交易 API

### 2.1 SnapTrade — 美系券商聚合器

- 覆盖：**35+ 零售券商**，地区为 **美国、加拿大、欧洲、澳大利亚、印度**。含 Schwab（含下单）、Fidelity、Robinhood、E*TRADE、Vanguard、Alpaca、eToro、DEGIRO、Binance、Coinbase 等；**IBKR 仅支持数据读取、不支持交易**。**无香港/新加坡/日本券商**。
- 只读：支持。Launch 档有专门的"每日数据只读"计费（$1/connected user/月，不含交易），Snowball Analytics、Kubera、Wealthfolio Connect 均以其做只读同步；SOC 2 Type II。
- 费用：**Build 免费档 $0、最多 5 个连接账户**（个人自用刚好够）；Launch $100/月平台费 + $1–2/connected user；按用户而非按账户计费。
- 结论：有美股多券商（Schwab/Fidelity/Vanguard 等）时的省事方案；对港日新券商无用。

### 2.2 Interactive Brokers — Flex Query 最适合自用拉持仓

三套 API 对比：

| API | 依赖 | 会话 | 适合自用拉持仓？ |
|---|---|---|---|
| **Flex Query Web Service** | 无本地程序 | **无需登录维护**：Client Portal 里一次性生成 Flex token + Query ID，之后纯 HTTP 请求 | **最佳**：免费、EOD 快照（XML/CSV，含持仓/交易/NAV），社区有 ibkr-flex-sync 等现成工具 |
| Client Portal Web API | 本地 Client Portal Gateway (Java) | 浏览器 2FA 登录、会话需 tickle/维护，每天要重登（ibeam 可半自动化但脆弱） | 不适合无人值守；数据近实时 |
| TWS API | 本地 TWS 或 IB Gateway 常驻 | 需登录维持 | 功能最全但最重 |

- Flex 报告通常在收盘后生成，适合每日一次的 EOD 同步；这正是个人财富管理工具需要的节奏。
- 个人账户使用 API 读取自身数据无额外费用（行情数据再分发另受协议限制）。

### 2.3 Futu / moomoo OpenAPI（富途）

- 架构：必须本地/云端运行 **FutuOpenD 网关**（自定义 TCP 协议中转到富途服务器），SDK（Python 等）连 OpenD。
- 持仓/资产：`accinfo`（账户资产，含多币种现金）、`position_list`（持仓）等交易查询接口齐全；支持港股/美股/A股（视账户）。
- 只读：**没有独立只读开关**——OpenD 登录即具备交易权限；事实只读靠只调查询接口 + 交易需额外"解锁密码"这层屏障。
- 限制：一个账号最多 10 个 OpenD 终端同时在线；行情订阅权限与 APP 一致（按登录 IP 区分，存在"行情互踢"）；新账号需先完成激活步骤（如问卷）。**2022 年底起中国大陆新增用户无法开户（存量不受影响）**；模拟账户可用于调试。免费。
- 部署注意：OpenD 需常驻（NAS/小主机/VPS 均可），对"无头"自动化是最大运维负担。

### 2.4 Tiger Brokers OpenAPI（老虎证券）

- 条件：**开通老虎账户并入金后即可免费使用 OpenAPI**；在开发者页注册获取 `tiger_id` + RSA `private_key` + 账户号，官方 Python/Java/C# 等多语言 SDK。
- 市场：美股（股票/ETF/期权/期货）、港股（含窝轮/牛熊证）、新加坡、澳大利亚股票。**无 A 股**。
- 只读：同富途，无独立只读开关，持仓/资产查询接口（positions 等）属交易服务类接口，只调查询即可；注册后自动生成模拟账号可先调试。
- 免费；高级行情（港股 LV2 等）单独订阅。

### 2.5 LongPort OpenAPI（长桥）

- 条件：**长桥开户 + 开发者平台完成认证即可免费申请**；凭证为 App Key / App Secret / Access Token（新接入走 OAuth 2.0，`authorization_code` + `refresh_token`，生产发现地址 `openapi.longbridge.com`，内地 `.cn`）。
- 架构：**REST + WebSocket 直连云端，无需本地网关**——四家中部署最轻，天然适合无头服务器定时任务。
- 持仓/资产：`/trade/asset/stock` 等接口返回账户、股数、可用股数、均价、币种；SDK 由 Rust 底层提供 Python/Node/Rust/Java 等（注意：包名已从 `longport` 改为 `longbridge`）。
- 行情：基础免费、高级权限包付费；有服务端频率限制（SDK 内置节流）。港美股（+ A 股行情）。模拟账户可在开发者中心开通。

### 2.6 Alpaca — 美股 API-first

- 免佣美股券商，API 原生：positions、account、portfolio history 端点齐全；**paper trading 账户完全免费**，可全流程测试；live 账户也免费开放 API。
- 若用户美股在 Alpaca，这是体验最好的自用同步（无需 OAuth 聚合商）。

### 2.7 Charles Schwab Trader API

- 现状（2025–2026）：**对个人开放且活跃**。开发者中心申请 `trader-api--individual` 权限 → 建 app → 浏览器 OAuth 授权绑定自己的账户。
- 提供 REST + 流式 API；行情约 120 次/分钟限额；**无官方 sandbox**（旧 TD Ameritrade API 已对新用户关闭）。生态活跃（QuantConnect、Wealth-Lab、MCP server 等）。
- 个人拉持仓：Accounts & Trading 端点（positions/holdings）可用。

### 2.8 日本券商 — 无 API（见 1.6）

SBI/乐天/Monex 均无个人 API；日本持仓只能手动/CSV。若用户愿意把日本仓位集中到 IBKR 日本IB证券证券账户，则可被 Flex Query 覆盖。

---

## 3. 加密货币

- **CCXT**：2026 年仍活跃维护（v4.5.x，2026-09 仍在发版；104 家交易所 REST、76 家 WebSocket、7 家预测市场），JS/TS、Python、PHP、C#/.NET 多语言，统一 `fetch_balance` 接口可拉多交易所余额。免费开源。已有 MCP 封装可接 AI agent。
- **CoinGecko**：Demo 免费档 10,000 credits/月、约 100 次/分钟（`x-cg-demo-api-key` header），需署名、禁止商用；做个人估值足够。注意 CoinDesk Data 已于 2026-05-21 关闭免费档，CoinGecko 是剩余的主要免费选择。
- **链上直接读**：公开 RPC / Etherscan 类浏览器 API 免费拉地址余额（冷钱包场景），不依赖任何聚合商。

---

## 4. 对比表

| API | 类型 | 地区覆盖(HK/SG/JP/US/CN) | 个人可用性 | 费用 | 只读支持 | 本地网关依赖 | 合规注意 |
|---|---|---|---|---|---|---|---|
| GoCardless BAD | 银行聚合 | 仅欧洲（HK/SG/JP/US ✗） | **新注册已关闭** | 老用户免费(50连接/月) | 是(天生只读AIS) | 无 | 产品 sunset 中 |
| Plaid | 银行+投资聚合 | US/CA/UK/EU（亚太 ✗） | 高（历史100免费item） | 按量/销售报价 | 是 | 无 | 仅美欧银行；亚太无用 |
| TrueLayer / Tink / Salt Edge | 银行聚合 | EU/UK 为主(Salt Edge 名义全球) | **低（企业向）** | 定制报价 | 是 | 无 | 个人基本无门 |
| Enable Banking | 银行聚合 | 欧洲 30 国 | **高（个人免费受限模式）** | 免费 | 是 | 无 | 仅欧洲账户 |
| HKMA Open API | 银行直连 | HK | **低（仅签约企业TSP）** | 银行商务条款 | Phase2 只读 | 无 | 个人无法注册TSP |
| SGFinDex | 银行聚合 | SG | **低（机构准入）** | — | 是 | 无 | 需FAPI/Singpass合规 |
| 日本银行/券商 | 直连 | JP | **无个人API** | — | — | — | CSV导入唯一路径 |
| SnapTrade | 券商聚合 | US/CA/EU/AU/IN（亚太券商 ✗） | 高 | 免费5连接；$100/月+$1–2/用户 | **有只读档** | 无 | SOC2；IBKR仅读 |
| IBKR Flex Query | 券商直连 | 全球IBKR账户(含港日美) | **高（个人账户原生）** | 免费 | 天生只读(报表) | **无** | EOD数据，行情再分发受限 |
| IBKR CP Web API / TWS | 券商直连 | 同上 | 高 | 免费 | 部分 | **有**（Gateway/TWS常驻） | 会话维护繁琐 |
| Futu OpenAPI | 券商直连 | HK/US/CN-A | 高（需牛牛账户） | 免费 | 无开关，事实只读 | **有**（OpenD常驻） | 大陆新用户无法开户；行情互踢；交易需解锁密码 |
| Tiger OpenAPI | 券商直连 | HK/US/SG/AU | 高（开户入金即用） | 免费 | 无开关，事实只读 | 无（直连） | RSA私钥保管；高级行情付费 |
| LongPort OpenAPI | 券商直连 | HK/US/CN-A | 高（开户+开发者认证） | 免费（基础） | 无开关，事实只读 | **无（直连云端）** | OAuth凭证保管；行情权限包 |
| Alpaca | 券商直连 | US | **极高** | 免费(paper/live API免费) | 读+可只下paper | 无 | 仅美股 |
| Schwab Trader API | 券商直连 | US | 高（个人权限可申请） | 免费 | 读+写均可 | 无 | 无官方sandbox；~120req/min |
| CCXT | 加密聚合 | 全球100+交易所 | 极高 | 免费开源 | 读+写 | 无 | 自管API key，建议只读key |
| CoinGecko / 链上 | 加密估值 | 全球 | 极高 | Demo免费10k/月 | 只读 | 无 | 署名+非商用 |

---

## 5. 架构建议（针对持有港美股 + 日本仓位的中文用户）

### MVP（0–2 个月）：全手动/文件导入，先把数据模型立稳

- 统一数据模型：`账户(机构/币种/类型) → 持仓快照(日期) + 交易流水`，多币种现金余额表（USD/HKD/JPY/CNY），每快照记汇率。
- 导入器优先级：券商 CSV（IBKR Flex 手动导出、长桥/富途/老虎 App 导出、SBI/乐天 CSV）→ 通用 CSV 映射器 → OFX/QIF（美系银行）。IBKR 的 Flex 报告格式本身就可以在 MVP 阶段手动下载、程序解析，为 V2 自动化直接铺路。
- 汇率：公开免费汇率 API + CoinGecko Demo 估值加密资产。
- 关键：**凭证与文件全部本地存储**（本地 SQLite + 系统 keychain），从一开始就按"用户自带凭证、只读"设计。

### V2（按优先级接入自动同步）

1. **IBKR Flex Query**（第一优先）：免费、无网关、无会话维护、EOD 快照，一套覆盖用户在 IBKR 的美股/港股/日本仓位；实现成本最低、稳定性最高。
2. **LongPort OpenAPI**（第二）：无本地网关、OAuth token 长期有效，云函数/家中小主机定时拉 `/trade/asset/stock` 即可；港美股中文用户的轻量首选。
3. **Tiger OpenAPI**（第三）：同样免网关，RSA 签名直连；用户若老虎持仓多则接。
4. **Futu OpenAPI**（第四，条件接入）：能力最全但需 OpenD 常驻；仅在用户有富途账户且愿意跑常驻网关（NAS/树莓派）时接；只调 `accinfo`/`position_list`，绝不碰下单接口，交易解锁密码留作安全屏障。
5. **美股补充**：有 Alpaca 账户直连 Alpaca；Schwab 用户走 Trader API 个人 OAuth；多美股券商（Fidelity/Vanguard/Robinhood）用户走 **SnapTrade 免费档（5 连接，只读 daily data）** 一把抓。
6. **加密**：CCXT 只读 key 拉各所余额 + CoinGecko 估值 + 公链 RPC 读冷钱包。
7. **银行**：美国账户 → Plaid（个人档，能注册则用）；欧洲账户 → Enable Banking；**香港/新加坡/日本银行自动同步放弃**（结构性不可行），长期以"导出文件投递文件夹 + 自动解析"的半自动方式覆盖。

### 设计原则

- **只读优先**：所有券商连接只实现查询类接口；Futu/Tiger/LongPort 无只读开关，靠"不实现下单代码 + 密钥最小权限 + 交易密码屏障"三重防线。
- **用户自带凭证**：工具不托管任何账户密码；token/私钥存本机 keychain；OAuth 走本机 localhost 回调。
- **EOD 快照模型**：所有源统一为"每日一次快照 + 事件流水"，与 Flex Query 的天然节奏对齐，避免实时推送复杂度。
- **降级路径**：每个自动连接器都保留 CSV 手动导入作为 fallback（银行端 CSV 是港日新的常态而非降级）。

---

## 6. 主要来源

- GoCardless BAD 停止新注册：github.com/OCA/bank-statement-import issue #867；actualbudget.org 文档；openbankingtracker.com
- Plaid 覆盖与计费：plaid.com/pricing；fintechmagazine.com；sahin.io
- TrueLayer/Tink/Salt Edge：blog.finexer.com（2025 TrueLayer 替代指南）；trio.dev；docs.saltedge.com
- Enable Banking：enablebanking.com；docs.firefly-iii.org
- HKMA Open API：hkma.gov.hk 银行业开放API 页；bochk.com TSP 条款；digfingroup.com（Phase 2 进度）
- 日本：Chambers Fintech 2026 Japan；Money Forward 相关报道
- 新加坡 SGFinDex：MAS 相关资料；globalinvestments.net（2026 Open Banking for Expats）
- SnapTrade：snaptrade.com/pricing；snaptrade.com/brokerage-integrations
- IBKR：ibkrguides.com（Flex Web Service v3 文档，2026-02 更新）；interactivebrokers.github.io（TWS API）；github.com Voyz/ibeam
- Futu：openapi.futunn.com/futu-api-doc；openapi.moomoo.com（OpenD 限制/互踢）
- Tiger：github.com/tigerfintech/openapi-python-sdk；docs.itigerup.com
- LongPort：open.longbridge.com/zh-CN/docs（/trade/asset/stock 等）
- Alpaca：alpaca.markets/docs
- Schwab：developer.schwab.com；github CF_schwab-API
- CCXT：docs.ccxt.com（104 REST/76 WS，2026-09）；github.com/ccxt/ccxt
- CoinGecko：coinmarketcap.com（Demo 10k credits 对比）；rfp.wiki（2026 对比）
