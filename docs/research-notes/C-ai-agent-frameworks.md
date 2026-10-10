# AI 金融 Agent 开源项目架构调研报告

**调研日期**：2026-10-03 · 方法：`gh api` 直读各仓库元数据、README、关键源码目录与设计文档

---

## 1. OpenBB（openbq-org/OpenBB，73.8k★，Python）

**架构概览**：定位是 "connect once, consume everywhere" 的数据基础设施层，不是 agent 框架。三层组成：① `openbb-core` 运行时（不 ships 任何数据，通过 entry points 动态发现已安装扩展并拼装成一个 typed Python client `from openbb import obb`）；② `extensions/`（Router 定义命令命名空间如 `obb.equity`/`obb.economy`，共 13 个领域包 + `platform_api` FastAPI 服务 + `mcp_server`）；③ `providers/`（20 个数据源实现包：SEC、FRED、Nasdaq、ECB、OECD、CBOE、TMX 等）。一套数据可同时服务 Python、REST API、OpenBB Workspace、Excel、MCP server 五种消费面。

**数据标准化层（核心可借鉴）**：Router 声明命令签名 + 标准 `DataModel`（Pydantic），Provider 通过 `Fetcher` 实现同一命令；上层代码只面对统一 schema，换数据源零成本。每个 provider 一个独立 pip 包、独立凭据（`bls_api_key` 等），可插拔组合。`openbb-mcp` 扩展把**已安装的全部命令自动暴露为 MCP tools**——数据层写一次，agent 工具层免费获得。

**Agent/Workspace 能力**：`agents-for-openbb` 仓库提供 20+ 个 agent 模板（prompt 优化器、raw widget data、reasoning steps、**带 citation 的数据引用**、charts/tables/PDF 产物、MCP tools、HTML artifacts、feedback 循环），基于 OpenBB AI SDK；另有 TypeScript 生产级参考 Agent Rita。AI 侧被刻意做薄：LLM 只负责编排和叙述，数据契约全部在 Platform 层。

**防幻觉**：数据经 Pydantic 校验后进入 agent；citation 模板证明其路线是"数据可溯源到 widget/API 调用"。
**可借鉴**：① Router+Provider+标准 DataModel 三分离——个人财富 OS 的"数据 agent"应做成统一 schema 网关而非各自为政的爬虫；② `openbb-mcp` 模式：一套命令树自动生成 MCP 工具集，9 个 agent 共享同一个数据 MCP；③ Workspace 的 reasoning-steps + citations UI 模式。

---

## 2. virattt/ai-hedge-fund（63.8k★，Python）

**架构概览**：已从早期"多 agent 互相聊天"演进为**流水线 + 信号抽象**。无 LangGraph/CrewAI，用 LangChain 各家 client + 自研 pipeline。关键抽象：`AlphaModel`（量化模型与 LLM persona 实现同一接口，输出统一 `Signal`）。`LLMAgent` 基类持有全部机制，persona（Buffett/Munger/Lynch/Graham/Druckenmiller）**只是一个 name + system prompt 子类**（`signals/buffett.py` 全文 40 行）。决策流程：`pipeline/stages.py` 两阶段——`assess_fund`（分析师只读 point-in-time `FundamentalsSnapshot`，产出验证过的目标权重 DecisionRecord，无订单）→ `execute_decision`（在后续收盘价上定仓成单，产出 CycleRecord）。基金定义在 `~/.hedge-fund/mandates/` YAML（策略、资本、节奏、不含 ticker）。

**输入输出设计（重点）**：每个 analyst agent 的输入是**结构化基本面快照**（不是自由文本），prompt 里带 checklist（Buffett 的 6 步检查清单），输出被强制为 `{bullish|neutral|bearish}` 折算成 ±1/0 信号 + metadata。**失败契约**：数据层错误向上传播（fail loud，坏快照绝不静默变 neutral）；LLM 调用/解析失败则 ABSTAIN（`Signal(value=0.0, abstained=True)`）；每次 LLM 决策持久化完整 prompt+response（PromptCache），同一快照绝不二次付费。回测时开 `blind` 模式——隐藏 ticker/行业/日期/美元值，防止 LLM 靠记忆作弊（市值只给分位数）。

**防幻觉**：盲化回测 + prompt 缓存审计 + hash-chained 账本（paper 目录，NAV 是 track record 不是 reset）+ 执行前人工审批步骤。
**可借鉴**：① "persona = system prompt 子类 + 统一 Signal 接口"——教育 agent/机会发现 agent 都可以这样标准化；② ABSTAIN 语义：数据不足就弃权，永远不算编造；③ assess 与 execute 分离在时间上（决策日 vs 成交日），天然防 look-ahead。

---

## 3. TauricResearch/TradingAgents（109.6k★，Python）

**架构概览**：**LangGraph**（langgraph>=1.2 + sqlite checkpointer 断点续跑）。图拓扑 = 仿交易公司组织架构：Analyst Team（market/social/news/fundamentals 四分析师**并行**执行、各自工具）→ Researcher Team（bull/bear 多轮结构化辩论，`count` 计数到 `max_debate_rounds`）→ Trader（综合决策）→ Risk Management（3 个风格渐趋保守的风险评论者 + 风险辩论）→ Portfolio Manager（用结构化输出批准/否决）。深度/快速双模型（deep_think vs quick_think）。

**辩论机制**：bull/bear node 各自把对方最新论点、四份分析师报告、完整对话 history 注入 prompt，要求 "engaging directly with the bear analyst's points 而非罗列数据"；round 数可配，结束后进 research manager 裁决。

**工具层**：`dataflows/vendors/`——SEC EDGAR（财报 as filed）、Alpha Vantage（含 look-ahead 过滤）、FRED 宏观、Reddit/Stocktwits 情绪、Yahoo、Polymarket；v0.5 强调 **point-in-time integrity**：所有带日期路径只允许看到分析日之前已发布的数据。

**防幻觉**：① **结构化输出 + 抗污染解析**：`schemas.py` 把 LLM 写的 "N/A"/"15%"（百分比误当价格）/"$1,234.50" 等脏值显式清洗，宁可丢一个字段也不丢整个决策；② 每份报告头部记录"是什么产生了它"——模型、版本、辩论轮数、数据 vendor 清单（可复现性）；③ Trader 价格 grounding；④ `memory/reflection.py` 沉淀历史决策经验。
**输出结构**：`reporting.py` 写报告树——按 analysts/research/trading/risk/portfolio 分节 markdown + 汇总 `complete_report.md`，头部含全部运行设置。
**可借鉴**：① bull/bear 辩论 + 裁决是最值得抄进"机会发现 agent"的对冲确认机制；② 报告头记录生成环境（模型/数据源/日期）作为"可审计元数据"；③ 双速模型分工（便宜模型跑分析、贵模型跑裁决）。

---

## 4. AI4Finance FinRobot（8.1k★）与 FinGPT（21.3k★）

**FinRobot 架构（三代演进本身就是教材）**：V0=AutoGen（教育）；V1=OpenAI Agents SDK（Web 报告生成器 `finrobot_equity/`）；**V2=PydanticAI（生产版 `finrobot_desktop/`，Tauri+FastAPI+React 桌面）**；V3=DeepSeek-Harness 在研。哲学："models reason, software computes, agents orchestrate, and systems verify."

**V2 核心设计**：① **9 个 agent，指令全是 markdown 文件**（`engine/agents/instructions/`，改行为不动 Python）——5 个流水线 agent（data→analysis→modeling→synthesis→report）+ 3 个辩论 agent（bull/bear/judge）+ 1 个 lead orchestrator；② **7 条 typed pipeline**（equity_research/dcf/ddm/lbo/comps/earnings/ic_memo），每步带 validator 和 retry；③ **32 个确定性算子**（DCF/DDM/LBO/comps/Monte Carlo/SOTP 全部纯 Python 计算，LLM 只叙述，"模型永远不能产出一个追溯不到函数调用的数字"）；④ **6 个审计算子**（`narrative_divergence`、`narrative_numeric_grounding`、`currency_caliber`、`ev_bridge`、`sector_sign`、`ttm_period`）**在报告发布前检查叙述与数字是否漂移**；⑤ 7 个数据 provider 带 failover + 响应校验（坏 payload 到不了计算层）；⑥ 产物 = 13 章报告（含价格目标区间、模型置信度、审计算子提出的 caveat），SQLite artifact store。DCF 表格在 UI 上直接标注 "code-computed"。

**FinGPT**：非 agent，是金融 LLM 底座（LoRA 微调、情感分析 benchmark、Forecaster、RAG、MultiAgentsRAG notebook）。`FinGPT_Forecaster` 是早期"新闻+股价→一周预测报告"流水线样板。对个人财富 OS 的意义：作为可本地部署的廉价情感/摘要模型，接在"新闻 agent/X 情报 agent"下游。

**可借鉴**：① "数字出自代码、叙述出自 LLM、输出全量 provenance"三原则 + 叙事审计算子（防幻觉的最强工程化答案）；② agent 指令 markdown 外置；③ 13 章报告 + 置信度 + caveat 的产物结构。

---

## 5. RUC-NLPIR/FinSight（ACL 2026 Main，274★）

**架构概览**：multi-stage、memory-centric 流水线：Data Collection → Analysis+VLM 图表精修 → Report drafting/polishing → Rendering。编排是**自研的 Programmable Code Agent（CAVM：Code Agent with Variable Memory）**——所有 agent 在一个共享变量空间里执行 Python 代码来操作数据/工具/记忆，而非固定 DAG；支持 checkpoint/resume、沙箱硬化（超时、受限 import）、API 限流。

**Agent 编制**（4 类）：Data Collector（路由收集结构化/非结构化数据）→ Deep Search Agent（multi-hop 搜索+抓取，带来源验证）→ Data Analyzer（code-first 分析 + 画图 + **VLM critique loop**：视觉 agent 按专业制图标准自动纠正缺图例/错刻度/低信息密度）→ Report Generator（outline→分节→润色→封面/参考文献→Pandoc 渲染 MD/DOCX/PDF）。

**信息源**：约 40 个工具，三类——金融数据 API（A 股/港股/美股三大报表、估值、股东、yfinance 美股、FRED 美宏观）、宏观/行业指标（GDP/CPI/PMI/LPR/社融/EPU 等）、Web 搜索/爬取（Serper/Bing/Bocha/DuckDuckGo/站内搜索/Playwright）。

**防幻觉/引用**：**Chain-of-Analysis**——每个结论都可回溯到透明分析链 + 严格 citation 指回原始数据源。
**输出**：2 万字+、多模态（图+表+参考文献）、publication-ready 报告；配置化 target_type（公司/宏观/行业/通用）与自定义 collect tasks。
**可借鉴**：① VLM 审图反馈环（AI 生成的图表先自检再进报告）；② Deep Research 的"搜索→验证→成文"独立子 agent 化，可整体移植为"财报 agent"或"机会发现 agent"的深研模式；③ outline→分节→润色→参考文献的报告生成分阶段。

---

## 6. juanjuandog/FinSight-AI（1.06k★，Java/Spring Boot）

**架构概览**：与 #5 同名但完全不同——A 股投研工作台，**后端工程可靠性参考**。Spring Boot 3.3（领域状态+编排）+ FastAPI AI sidecar（embedding/rerank/generation，模型可换且有确定性 fallback）+ PostgreSQL/pgvector + Redis + RabbitMQ。无 LLM 编排框架，工作流是**显式状态机**：CREATED→LEASE_ACQUIRED→INGESTING→METRIC_CALCULATING→DOCUMENT_INDEXING→INTELLIGENCE_BUILDING→AI_ANALYZING→SUCCEEDED/FAILED→RECOVERING/DEAD_LETTER。

**Evidence-grounded RAG**：FTS（JSONB 全文）+ pgvector 向量双召回 → **RRF 倒数排名融合** → cross-encoder 重排 → 输出 evidence trace，且有 RAG 回归评估。

**报告版本化与质量审计（重点）**：报告绑定 `dataSnapshotHash + contextHash + reportVersion`——数据变了缓存自动失效，杜绝"陈旧报告冒充新结论"；每次 AI 分析留存证据路径、模型来源、快照哈希，可 diff 可导出。
**长任务可靠性**：幂等键提交（repository 级 createIfAbsent）、Redis Lua 单飞租约 + fencing token（旧 worker 不能覆盖新状态）、超时扫描恢复、死信处理。
**可借鉴**：① snapshot-hash 绑定报告 = "每份 daily brief 标注它看到的数据版本"；② evidence trace + RAG 回归评估套件；③ AI 作为可替换 sidecar、领域状态与模型解耦的进程拓扑。

---

## 7. questflowai/investorskills（1.88k★，Swift/Markdown）

**架构概览**：无代码框架，是**"投资判断的技能包格式"**：把巴菲特/利弗莫尔等人的判断力结构化为可移植 plain-text 包。每包 = `SKILL.md`（触发条件、输入、流程、输出格式、guardrails）+ 可选 `invest.md`（YAML frontmatter 机器可读：signals 带权重/频率/方向/阈值、filters、sizing 上限、risk 参数、marketRegime、decisionCadence + Markdown 散文：世界观、执行规则、行为护栏）。带模板、spec、书单/播客/视频源列表。可在 Claude Code/Codex/Cursor 等任何能读 SKILL.md 的 harness 中运行。

**可借鉴**：① **判断即数据**——"教育 agent"不必现场生成投资哲学，而是加载结构化 INVEST.md；② YAML（机器）+ 散文（人读）双态 schema；③ 每个判断系统强制带 invalidation 条件与 sizing 上限字段——这是给"机会发现 agent"装风险护栏的现成格式。

---

## 8. BlockRunAI/awesome-finance-mcp（219★）——精选 MCP Server

与"个人财富管理/行情/新闻/财报"最相关的 7 个：

| MCP Server | 功能 | 对 9-agent 的价值 |
|---|---|---|
| **OpenBB Platform（openbb-mcp）** | 全部 OpenBB 命令一键变 MCP 工具（股票/宏观/新闻/报表） | 数据 agent 的统一底座，免费 |
| **Financial Datasets MCP** | 利润表/资产负债表/股价 | 财报 agent 首选，ai-hedge-fund 同源 |
| **FRED MCP**（stefanoamorelli） | 美联储宏观数据 | 宏观/组合 agent 的利率、CPI 输入 |
| **Finnhub MCP**（stock-market-mcp-server） | 行情+新闻+情绪 | 行情 agent + 新闻 agent |
| **Edgrapi / Equibles** | SEC EDGAR：8-K/13F/13D-G/内幕交易/XBRL 全文检索 | 财报 agent 的 filing 级证据 |
| **BankBridge / Monarch Money MCP** | 只读银行余额、交易、现金流（Plaid） | Personal CFO 的净资产/现金流入口 |
| **FilingFirehose MCP**（hosted） | 8-K 条目检测、激进股东标签、法证风险分 | 机会/风险事件触发器 |
| （备选）**Yahoo Finance MCP**（maxscheijen） | 免费行情 | 零成本兜底行情源 |

---

## 9. Kingler16/Velora（40★，活跃，Python）

**架构概览**：个人财富顾问，**不调 API，shell out 到 Claude Code CLI `--print` 模式**（用 Max/Pro 订阅，零 API 财务成本）。Cron/Telegram/Web → `data/`（market=yfinance、macro=FRED+ECB+恐惧贪婪指数、news=Brave+Bloomberg RSS+Finnhub、calendar=财报日历）→ cache → `analysis/claude.py`（Opus high effort，prompt 经 stdin）→ memory（briefings/recommendations/theses 持久记忆）→ Telegram + Web（FastAPI+HTMX+Chart.js，7 页面，树莓派 90MB 可跑）。

**每日简报实现（重点）**：system prompt 是 9 段规则化的"资深顾问合同"：① **数据完整性**——绝不编造数字，无数据就说无数据，且强制标注 `[Fakt]/[Berechnung]/[Einschätzung]`（事实/推算/观点三色标签）；② **"不行动是合法且常是最优建议"**；③ 深度要求（牛/基准/熊情景+触发器、跨资产相关性、内幕交易信号）；④ **防复读**——注入历史 briefing 记忆，只讲增量；⑤ 新标的来自 watchlist+规则 screener，且给的是可自算的原始指标（ATR/RSI/SMA200）而非他人评级；⑥ 新闻带时效标签（>7 天不得用于战术判断）；⑦ 税务上下文；⑧ 风险画像 + 单次建议不超过组合 5-10% 的硬护栏。简报结构：MARKTLAGE（市况）→ PORTFOLIO-CHECK（逐持仓）→ EMPFEHLUNGEN。
**推荐闭环**：BUY/SELL/WATCH 卡片持久化，自动检测结果、统计命中率，Telegram 自然语言记账自动关闭对应推荐。
**可借鉴**：① [事实/推算/观点] 三标签是个人版最轻量的防幻觉标注，直接可抄进 daily brief；② 推荐命中率统计（agent 自我问责）；③ Claude Code CLI 省成本模式。

---

## 10. kunkundi/niuone（315★，Python+Vue）

**架构概览**：A 股本地优先投研工作台，非 LLM 框架——**领域分层单体**（core/automation/backtesting/dashboard/market_data/messaging/monitoring/reports/screening/strategies/trading，依赖单向）。LLM 用在窄缝：自然语言策略起草（`prompt_refinement.py` **只在创建期调用模型**，输出编译为不可变规则计划，运行期纯本地）、消息摘要、盘面报告增强。

**最独特的设计（重点）**：① **协议冻结（protocol freezing）**：严格前向评估在开盘前对策略源码、配置、账户基线做 SHA-256 指纹锁定，版本号 v18→v51 逐条演进并归档，"代码漂移只写诊断并阻断晋级，不覆盖原锁"；② **策略身份不可变**：文字策略编译成带引擎版本/特征版本/SHA-256 的执行计划，编译器**拒绝任意代码、未注册特征、运行期 model_judgment**，缺数据一律 `unknown` 且失败关闭；③ **五阶段漏斗审计**：观察候选→决策池→模型 BUY→实际 BUY，每阶段落 SQLite 耐久证据，决策与成交两侧不一致即 `operations_blocked`；④ 成效声明门槛：≥30 笔完整生命周期 + Wilson 95% 下界>50% + 最大回撤≤6% 等硬指标；⑤ 题材生命周期状态机（酝酿→主升→高潮→分歧→退幕）与执行动作分离。
**可借鉴**：① "LLM 起草、规则引擎执行"——Personal CFO 的建议生成与执行同样应分离；② 决策漏斗全留痕 + 结果验证统计；③ 快讯按"发布时间可靠性+下一交易日边界"过滤后才允许进入决策证据。

---

## 横向对比表

| 项目 | 编排框架 | Agent 拓扑 | 数据源 | 防幻觉/引用机制 | 报告产物 |
|---|---|---|---|---|---|
| OpenBB | 无（数据平台） | 无 agent，MCP 暴露 | 20 provider，标准 DataModel | Pydantic 契约 + citation 模板 | Workspace widgets |
| ai-hedge-fund | LangChain+自研 pipeline | persona=Signal 子类，assess→execute | Financial Datasets（PIT 快照） | ABSTAIN/盲化回测/prompt 缓存 | 决策记录+hash 链账本 |
| TradingAgents | LangGraph | 4 分析师并行→bull/bear 辩论→风险辩论→PM | EDGAR/FRED/Reddit/Stocktwits 等 | PIT 完整性+脏值清洗+报告头溯源 | 分节 markdown 报告树 |
| FinRobot | PydanticAI（V2） | lead+5 流水线+3 辩论 | 7 provider failover | 确定性算子+6 审计算子 | 13 章报告+置信度+caveat |
| FinGPT | 无（模型层） | — | 金融语料 | 微调+RAG | 预测/情感输出 |
| FinSight(RUC) | 自研 CAVM | 采集→深搜→分析→成文 | 40 工具+多搜索引擎 | Chain-of-Analysis+citation | 2 万字 MD/DOCX/PDF |
| FinSight-AI | Spring 状态机 | 阶段化工作流 | A 股+公告 | 混合 RAG+evidence trace+快照哈希 | 版本化报告可 diff |
| investorskills | 纯文本技能包 | 判断即配置 | 书单/播客源 | guardrails 内置 | SKILL 输出格式 |
| Velora | 无（单 prompt+CLI） | 单顾问+记忆 | yfinance/FRED/ECB/Brave | 三色标签+无数据即说+时效过滤 | Telegram 简报三段式 |
| niuone | 自研规则引擎 | LLM 仅起草 | 东财/腾讯/新浪/NewsNow | 协议冻结+失败关闭+漏斗审计 | 盘前/午盘/盘后报告 |

---

## 多 agent 金融系统的 8 条最佳实践

1. **数字出自代码，叙述出自 LLM**（FinRobot/ai-hedge-fund/OpenBB 共识）：估值、收益、指标一律确定性计算，LLM 只解释与综合；凡报告中的数字必须能追溯到函数调用或 API 响应。这是防幻觉的第一道墙。

2. **统一数据契约层，agent 只面对标准 schema**（OpenBB Router+Provider 模式）：9 个 agent 不要各接各的 API；建一个标准 DataModel 网关并自动导出 MCP 工具（openbb-mcp 模式），数据源可替换、凭据集中、换源零改动。

3. **结构化信号接口 + 弃权语义**（ai-hedge-fund）：每个 analyst agent 输出统一 `Signal{方向/强度/置信度/metadata}`；数据不足 ABSTAIN 而非中性，LLM 失败弃权而数据失败 fail-loud。下游（组合分析/Personal CFO）可以盲组合。

4. **对抗式确认：bull/bear 辩论 + 独立裁决**（TradingAgents/FinRobot）：机会发现 agent 的产出先经正反方多轮互驳再裁决，且辩论轮数、参与模型写入报告元数据——这比"再检查一遍"有效得多。

5. **证据链与版本绑定**（FinSight 系双雄）：每条结论挂 citation/Chain-of-Analysis；每份报告绑定 `dataSnapshotHash+contextHash+version`，数据更新即失效；建议落库后自动做结果验证与命中率统计（Velora/niuone）。

6. **叙事审计算子**（FinRobot 独有但值得普及）：发布前用确定性检查器比对 LLM 文本与底层数字——方向是否一致、币种口径、期间口径、叙述偏离度——不通过就拦截并标注 caveat。

7. **决策与执行在时间和权限上分离**（ai-hedge-fund assess/execute、niuone 起草/编译执行）：分析 agent 永不直接下单；LLM 起草的策略编译为不可变规则计划、带指纹冻结、失败关闭；执行前人工审批（approval step）+ 硬风控限额（Velora 单次 ≤5-10% 组合）。

8. **判断资产化与自我问责**（investorskills + Velora + niuone）：投资哲学沉淀为可加载的 SKILL/INVEST.md（带 invalidation 条件与 sizing 上限），历史简报注入记忆只讲增量（防复读），推荐闭环统计命中率，成效声明设硬性样本量与置信下界门槛——让 agent 的"资历"随使用积累且可审计。
