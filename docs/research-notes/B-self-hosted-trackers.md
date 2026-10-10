# 开源个人理财/组合追踪项目调研报告（2026-10-03）

数据来源：GitHub API（`gh api`，star/推送时间/贡献者/发版均为当日实测）+ 仓库源码关键词检索（SnapTrade/GoCardless/AI/MCP 等命中数）。活跃度以"近 3 个月（2026-07-03 起）commit 数"量化，100 为分页上限，实际可能更多。

---

## 1. wealthfolio/wealthfolio — Rust/Tauri 桌面端（综合最优）

- **现状**：9,109 stars，AGPL-3.0（+TRADEMARKS 商标限制），最后推送 2026-10-03，**极度活跃**（100+ commits/3mo，80 贡献者，v3.9.1 于 9/27 发版）。v3 已完成大重构：monorepo（apps/frontend + Rust crates/*），新增消费追踪、Docker 自托管、iOS App。
- **数据模型**：本地 SQLite（crates/storage-sqlite）；核心为账户 + Activities（交易/股息/转账）+ holdings/估值历史；v3 新增 spending 块；有 addon SDK（packages/addon-sdk）支持插件扩展。
- **行情**：内置 provider registry + resolver（crates/market-data/src/provider）：**Yahoo、Alpha Vantage、Finnhub、marketdata.app、Boerse Frankfurt、Metal Price API（贵金属）、OpenFIGI（证券标识）、美国国债收益率**——开源项目里行情源最广的之一，BYO API key。
- **自动同步**：免费层仅手动/CSV；**Wealthfolio Connect**（可选订阅）提供 30+ 券商只读同步 + 加密多设备同步，底层为 **SnapTrade**（代码 29 处命中，crates/connect/broker/mapping.rs）。Connect 的认证走其公开 Supabase 配置，付费需订阅。
- **分析**：TWR/MWR 真实回报、基准对比、多币种净值、消费、模拟（net-worth/profiles 模拟测试）；FIRE 计算弱于 Ghostfolio。
- **AI**：**全清单最强**。crates/ai：基于 rig-core 的 LLM 编排，支持 OpenAI/Anthropic/Gemini/Groq/**Ollama（本地）**/OpenRouter（BYOK），带 tool registry、system prompt、eval 框架；crates/agent-tools + **wealthfolio-mcp**：原生 MCP server 把本地金融数据暴露给任意 AI agent。整套就是"AI 财富 OS"的参考实现。
- **自托管**：桌面 app（mac/win/linux）+ Docker（compose.yml；docs/self-host 含 Proxmox/Unraid 模板），复杂度低-中。
- **安全**：local-first，数据全在设备；无云数据库；Connect 同步走加密通道。
- **可复用点**：① crates/ai + MCP 的"助手+工具注册表"架构；② 多行情源 provider registry/resolver；③ SnapTrade 券商同步映射层。

## 2. ghostfolio/ghostfolio — NestJS+Angular 自托管（数据模型标杆）

- **现状**：9,394 stars，AGPL-3.0，推送 2026-10-03，**极活跃**（100+ commits/3mo，100 贡献者，周更，3.77.0 于 10/2）。
- **数据模型**：Prisma + PostgreSQL，Activity 枚举完整（BUY/SELL/DIVIDEND/FEE/INTEREST/LIABILITY），SymbolProfile（symbol/assetClass/assetSubClass/currency）+ MarketData 快照，多币种靠 SymbolProfile.currency + 汇率换算；20 年思路沉淀的最干净 web 端组合模型。
- **行情**：provider 抽象层（apps/api/src/services/data-provider）：**Yahoo（默认免费）、Alpha Vantage、EOD Historical Data、Financial Modeling Prep、CoinGecko、Google Sheets（自定义 symbol）、RapidAPI、Manual + 官方 Ghostfolio 数据源**；部分高级数据在 Premium 订阅后。
- **自动同步**：**无银行/券商同步**（SnapTrade 0 命中），纯 CSV/导入——最大短板。
- **分析**：ROAI/TWR 多周期、资产配置、多币种净值、股息日历、**X-Ray 组合诊断（再平衡/风险）**、**FIRE 计算器**、静态风险分析。
- **AI**：无内置 LLM，但新增了**原生 MCP endpoint**（apps/api/src/app/endpoints/mcp/*，Access 类型支持 MCP token）——外部 AI agent 可凭 token 读组合。
- **自托管**：Docker 单容器 + Postgres + Redis，复杂度低；文档成熟。
- **安全**：自托管数据自持；匿名公开分享用 salt 保护 access token；Premium 云可选。
- **可复用点**：① Prisma Activity/SymbolProfile 数据模型；② 可插拔 data-provider 抽象；③ MCP access-token 接入模式。

## 3. maybe-finance/maybe — Ruby（已归档，遗产有价）

- **现状**：54,249 stars，**2025-07-24 归档**（v0.6.0 终版），3 个月 0 commit，100 贡献者。AGPL-3.0；README 明确："Maybe"是商标，fork 不得使用名称/Logo。
- **数据模型**：Family → Account（asset/liability）→ **Entry 多态（valuation/transaction/trade）**，Valuation 历史与交易统一建模，Security/Price/Holding；多币种字段。这是估值历史建模最优雅的方案之一。
- **行情**：依赖 Synth（synthfinance）API，无免费自带 provider；**同步**：无（计划中的 Synth/SnapTrade 未落地）；**分析**：净值趋势/账户分组，无 FIRE；**AI**：无。
- **自托管**：Docker 文档仍在，但无维护、有安全隐患，不建议生产使用。
- **可复用点**：① Account/Entry/Valuation 单表多态模型（直接抄 schema）；② 代码质量与设计文档；③ 仅作参考，勿当基座。

## 4. actualbudget/actual — TS 预算工具（同步/加密标杆）

- **现状**：29,275 stars，MIT（许可最宽松），推送 2026-10-03，**极活跃**（100+ commits/3mo，月更 v26.10.0，100 贡献者）。
- **数据模型**：信封预算优先：budget 文件（含 accounts/transactions/payees/rules/schedules），**CRDT（loot-core/crdt）做端到端合并同步**；投资组合非核心，无行情。
- **自动同步**：**插件式 bank-sync（服务端）**：内置 **GoCardless（164 处代码命中）+ SimpleFIN（64）+ PluggyAI**，provider 接口可自行扩展——最佳银行同步参考。
- **分析**：预算/收支报表/现金流；无组合分析、FIRE；**AI**：无（有新 plugins-service）。
- **自托管**：Docker 单容器（sync-server）或桌面 app；复杂度低。
- **安全**：**local-first + E2E 加密 budget 文件 + CRDT 多端同步**——隐私架构的行业标准。
- **可复用点**：① CRDT + E2E 加密同步架构；② pluggable bank-sync provider 接口（GoCardless 实现）；③ 规则/自动分类引擎。

## 5. firefly-iii/firefly-iii — PHP/Laravel（记账规则引擎）

- **现状**：24,806 stars，AGPL-3.0，推送 2026-10-03，极活跃（100+ commits/3mo，补丁日更 v6.7.7，100 贡献者）。
- **数据模型**：复式记账：Account（asset/expense/revenue/liability/cash）+ TransactionJournal（可拆分）+ Budget/Category/Tag/PiggyBank/Rule/Recurrence/Webhook；v6.1+ 内置多币种汇率表。
- **行情**：无投资行情源（仅 FX 汇率），组合追踪弱；**同步**：官方 **data-importer（独立容器，安全隔离）**：**GoCardless、Spectre、SALT Edge** + CSV/CLI/API 自动化导入。
- **分析**：收支/预算/分类报表丰富，规则引擎自动分类强；无组合分析/FIRE。
- **AI**：**无，且明确拒绝**——README 标语即 "No AI, no cloud and privacy-friendly"。
- **自托管**：Docker（app+importer+db 三容器）或 K8s；复杂度中。
- **可复用点**：① TransactionRule 规则引擎 + 自动分类；② importer 与核心分离的凭证安全架构；③ 复式账户类型体系。

## 6. ananthakumaran/paisa — TS+Go，ledger 核心（文本记账+仪表盘）

- **现状**：3,220 stars，AGPL-3.0，最后推送 2026-09-06（约 1 个月前），**单人维护**（10 贡献者，10 commits/3mo，v0.7.6）。低频但未死。
- **数据模型**：**纯文本 ledger（beancount/hledger）双录入** + YAML 配置，web UI 只读渲染——数据天然对 AI/工具链友好。
- **行情**：Yahoo（NSE/BSE/美股）+ 印度 AMFI 基金 NAV；**同步**：印度银行/券商 fetcher（Zerodha 等）via beancount importer，无 GoCardless。
- **分析**：净值、资产配置、XIRR、FIRE（印度语境）、税务报表。
- **AI**：无。**自托管**：Docker 或单二进制，极轻。
- **可复用点**：① "ledger 文本记账 + 只读仪表盘"模式（最适合 LLM 直接读写交易）；② importer 插件体系；③ XIRR/配置分析实现。

## 7. portfolio-performance/portfolio — Java 桌面（分析/行情之王）

- **现状**：4,084 stars，**EPL-1.0**（弱 copyleft，唯一非 AGPL/MIT 的强协议），推送 2026-10-03，极活跃（100+ commits/3mo，100 贡献者，约 6 周一版 0.87.0）。近 20 年演进。
- **数据模型**：最完整的投资模型：Security（+分组）、Portfolio/Account、全谱系交易类型（买卖/股息/转入/税费/期货），**Classification 资产类别多层树**，多币种 + 汇率历史。
- **行情**：内置行情源最多：Yahoo、AlphaVantage、EOD、Finnhub、generic JSON/XML/CSV feed、ECB 汇率、CoinGecko 等；杀手锏是 **PDF 账单导入器（几十家券商对账单→交易）**。
- **同步**：无自动银行同步（导入工作流）；**分析**：TWROR/IRR/TTWROR、资产配置树+再平衡、股息追踪、benchmark、德国税务特化——桌面端分析无对手。
- **AI**：无（仅 AGENTS.md/CLAUDE.md 供编码 agent）。**自托管**：桌面 app，不适合服务器，文件为本地 XML/JSON。
- **可复用点**：① Classification 树 + 再平衡计算；② PDF→交易导入器思路（LLM 可替代其正则）；③ 交易类型全谱系枚举。

## 8. rotki/rotki — Python（加密会计/隐私）

- **现状**：4,040 stars，AGPL-3.0（premium 附加服务闭源），推送 2026-10-02，活跃（100+ commits/3mo，100 贡献者，v1.44.1 于 10/2）。
- **数据模型**：加密资产为主 + 股票/手工条目；位置/时间戳资产余额快照、EVM 事件解码 pipeline；**SQLCipher 加密本地库**。
- **行情**：价格预言机链（CryptoCompare/CoinGecko/DefiLlama/manual）+ premium 历史数据；**同步**：30+ 交易所 API key、EVM 链上地址、BTC xpub；无银行同步。
- **分析**：加密会计引擎（PnL、损益事件、**税务报告**）、多币种净值、DeFi；股票弱。**AI**：无。**自托管**：Docker/桌面 app。
- **安全**：隐私设计最强——数据加密、本地、premium 只收匿名数据。
- **可复用点**：① 交易所 API 连接器矩阵；② 税务会计引擎；③ 加密本地存储设计。

## 9. RIP-Comm/sossoldi — Flutter 移动端

- **现状**：1,400 stars，MIT，推送 2026-09-12，**低频**（5 commits/3mo，57 贡献者，1.0.0 于 8/20 才发首个正式版）。
- **数据模型**：本地 SQLite：账户、收支/转账交易、预算、周期交易、净值快照、v1 新增投资（股/债/加密）；多币种基础。
- **行情**：无自动行情（手动）；**同步**：无（PSD2 仅在 roadmap）；**分析**：净值/预算，轻量；**AI**：无。
- **自托管**：纯本地 app，无服务器；**安全**：数据本地。
- **可复用点**：仅 MIT 许可下的移动端 UX/schema 参考；整体价值有限。

## 10. finanze/finanze — Python+TS 新秀（多资产聚合）

- **现状**：59 stars，AGPL-3.0，推送 2026-10-03，**活跃小项目**（68 commits/3mo，9 贡献者，v0.10.1 于 9/28）。注意：并非纯 TS——Python 3.13 后端（PyInstaller 打包桌面）+ TS 前端 + Docker。
- **数据模型**：聚合 banks/brokers/crowdfunding/crypto/**real estate** 于本地加密数据库；"实体（entities）"统一建模多资产。
- **行情**：内置开源数据源+手动；**同步**：**GoCardless（17 处命中）PSD2 银行同步**。
- **分析**：净值 dashboard、**房地产投资 KPI（少见）**、储蓄/退休多场景计算器、贡献预测。**AI**：无。
- **自托管**：Docker 或桌面单机；**可复用点**：① 房地产 KPI 建模；② Python 版 GoCardless 集成；③ 多资产类型聚合 schema。

## 11. Librefolio/LibreFolio — Python 新秀（多券商+FX）

- **现状**：20 stars，AGPL-3.0，推送 2026-09-30，**单人高强度**（100+ commits/3mo，1 贡献者，v1.1.0 于 9/7）。风险：bus factor=1。
- **数据模型**：资产/交易/贷款，多券商；特色是 **FX 汇率对 + 转换路由图（conversion routes）** 和 plugin 体系。
- **行情**：**yfinance 插件（138 处命中）** 自动定价 + 技术分析工具；**同步**：手动/导入。
- **AI**：无。**自托管**：docker-compose 单容器，简单。
- **可复用点**：① FX 转换路由建模（多币种清算思路）；② plugin 式行情源；③ 开发日志式文档结构。

## 12. privatefolio/privatefolio — TS"AI 财富管家"（已近停滞）

- **现状**：70 stars，LICENSE 文件实为 **AGPLv3**（GitHub 显示 NOASSERTION 因自定义头部与 "free*" 注记），最后推送 2026-06-13（近 4 个月），**0 commits/3mo**，3 贡献者，最后发版 2025-10——**实质停更**。
- **数据模型**：交易/账户/组合 + 税务，本地 SQLite；**行情**：Yahoo 等 + 手动；**同步**：无银行（仅 CSV）。
- **分析**：FIRE、波动率模拟、现金流预测、退休规划、税报——分析面广但深度一般。
- **AI**：无内置 LLM，定位是"**与 LLM/AI agent 配合使用的本地金融数据 toolkit**"（agent 直接读本地 API/SQLite）。
- **自托管**：Electron 桌面 + Fly.io；**可复用点**：① "为 agent 设计"的产品定位；② 模拟/退休计算模块；整体建议只取思路，勿依赖代码。

## 13. midday-ai/midday — TS 自由职业者财务（AI 最强但开源放缓）

- **现状**：15,060 stars，AGPL-3.0，最后推送 2026-06-13（约 3.7 个月前），**0 commits/3mo**，开源仓库自 0.5.0（2026-02）后明显放缓（重心疑似转闭源 SaaS），33 贡献者。
- **数据模型**：Supabase/Postgres：business/bank accounts/transactions/invoices/projects——**企业/自由职业者财务，非个人组合**。
- **行情**：无投资行情；**同步**：**开源项目里最全银行连接矩阵：packages/banking 抽象 + GoCardless/Plaid/Teller/EnableBanking 四 provider**。
- **分析**：经营财务概览、对账；无投资组合分析。**AI**：**最完整**——Vercel AI SDK（api/worker）、Assistant（bot）、**Magic Inbox（LLM+OCR 自动匹配收据/发票→交易）**、insights、**mcp-apps**。
- **自托管**：复杂——需 Supabase/Railway/Vercel/Cloudflare/Trigger.dev 全家桶，个人轻量自托管不现实。
- **可复用点**：① packages/banking 四 provider 抽象；② Magic Inbox "LLM 匹配票据→交易"模式；③ assistant + MCP 集成方式。

---

## 横向对比表

| 项目 | 技术栈 | 数据模型质量 | 行情源 | 自动同步 | 分析能力 | AI | 活跃度(3mo) | License | 最可复用点 |
|---|---|---|---|---|---|---|---|---|---|
| wealthfolio | Rust/Tauri+SQLite | 高 | Yahoo/AV/Finnhub/marketdata.app 等 8+ | SnapTrade（Connect 订阅） | TWR/MWR+净值+模拟 | **BYOK 助手+MCP** | 100+ commits，极活跃 | AGPL-3 | AI crate + provider registry |
| ghostfolio | NestJS+Angular+Prisma | **很高** | Yahoo/AV/EOD/FMP/CoinGecko 等 9 | 无（CSV） | 配置/X-Ray/FIRE | MCP endpoint | 100+，周更 | AGPL-3 | Prisma 模型+provider 抽象 |
| maybe | Ruby/Rails | 高（遗产） | Synth | 无 | 净值 | 无 | **已归档** | AGPL-3 | Entry/Valuation 模型 |
| actual | TS/Node+CRDT | 中（预算向） | 无 | GoCardless/SimpleFIN/PluggyAI | 预算报表 | 无 | 100+，月更 | **MIT** | CRDT+E2E 加密同步 |
| firefly-iii | PHP/Laravel | 高（记账向） | 仅 FX | GoCardless/Spectre/SaltEdge | 记账报表 | 明确拒绝 | 100+，日更 | AGPL-3 | 规则引擎+importer 分离 |
| paisa | TS+Go+ledger | 中（文本） | Yahoo+AMFI | 印度 fetcher | XIRR/FIRE | 无 | 10，单人 | AGPL-3 | ledger+仪表盘模式 |
| portfolio | Java 桌面 | **最高** | 最多+PDF 导入 | 无 | **最强（再平衡/股息/税）** | 无 | 100+，6 周一版 | EPL-1.0 | Classification 树+交易类型 |
| rotki | Python+Vue | 高（加密向） | 预言机链 | 交易所 30+/链上 | 加密会计/税报 | 无 | 100+ | AGPL-3 | 会计引擎+加密存储 |
| sossoldi | Flutter | 中低 | 无 | 无 | 净值/预算 | 无 | 5，低频 | MIT | 移动端 UX |
| finanze | Python+TS | 中 | 内置+手动 | GoCardless | 净值+房产 KPI+退休 | 无 | 68，活跃早期 | AGPL-3 | 房产 KPI+PSD2（Python） |
| LibreFolio | Python+TS | 中 | yfinance 插件 | 无 | 净值+技术分析 | 无 | 100+，单人 | AGPL-3 | FX 路由图 |
| privatefolio | TS/Electron | 中 | Yahoo+手动 | 无 | FIRE/模拟/退休 | agent 友好（无内置） | **0，停滞** | AGPL-3（自标） | "为 agent 设计"定位 |
| midday | Bun/TS/Supabase | 高（企业向） | 无 | **GoCardless/Plaid/Teller/EnableBanking** | 经营财务 | **最全（助手/Inbox/MCP）** | **0，放缓** | AGPL-3 | banking 抽象+Magic Inbox |

## 对"自建 AI 财富 OS"的核心结论

1. **首选基座二选一**：Ghostfolio（数据模型+9 行情源+FIRE+MCP，自托管成熟）或 Wealthfolio（AI 架构最完整：BYOK 助手+工具注册表+MCP server+SnapTrade 连接，但 Connect 同步要订阅）。两者皆 AGPL，商用 SaaS 需开源。
2. **拼图**：银行同步抄 midday 的 4-provider banking 抽象或 actual 的 bank-sync 接口（GoCardless 免费额度够个人用）；票据→交易匹配抄 midday Magic Inbox；再平衡/资产分类树抄 Portfolio Performance；多端加密同步抄 actual 的 CRDT+E2E。
3. **避坑**：maybe/privatefolio/midday 开源端均停更，只取设计勿做依赖；rotki 仅适合加密重仓场景；paisa/LibreFolio 是单点项目。行情源没有免费午餐——Yahoo 抓取随时可能被封，凡商业化必须预留付费 provider（EOD/FMP）切换层，ghostfolio 和 wealthfolio 的 provider 抽象正是为此设计。
