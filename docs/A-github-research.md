# A. GitHub Research — 开源项目深度调研总报告

**调研日期**：2026-10-03 · **方法**：GitHub API 实测（stars/push/contributors/release）+ 源码目录与关键词检索（SnapTrade/GoCardless/AI/MCP 命中数）+ 官方文档核对
**明细**：见 `research-notes/B-self-hosted-trackers.md`（13 个理财/追踪项目逐项深研）与 `research-notes/C-ai-agent-frameworks.md`（10 个 AI Agent 框架逐项深研）

## A1. 调研范围

共深研 **23 个项目**，覆盖 8 个方向：自托管组合追踪、预算记账、文本记账、桌面分析、AI 多 agent 框架、金融数据平台、新闻聚合、行情/分析库。

## A2. 总表（按定位分组，数据为 2026-10-03 实测）

### 第一梯队：与本产品愿景直接重合（基座候选）

| # | 项目 | Stars | 活跃度（3mo commits） | License | 技术栈 | 一句话定位 |
|---|---|---|---|---|---|---|
| 1 | **wealthfolio/wealthfolio** | 9,109 | 100+（极活跃，v3.9.1） | AGPL-3.0 | Rust/Tauri + SQLite | 本地优先桌面组合追踪，**内置 BYOK AI 助手 + MCP server + 8 家行情源 + SnapTrade 券商同步** |
| 2 | **ghostfolio/ghostfolio** | 9,394 | 100+（周更，3.77.0） | AGPL-3.0 | NestJS+Angular+Prisma | 自托管财富管理 web 端，**数据模型最干净 + 9 家行情源 + FIRE/X-Ray + MCP endpoint** |

### 第二梯队：解决了"我最难的技术问题"的单项冠军

| # | 项目 | Stars | 活跃度 | License | 难题 | 它的答案 |
|---|---|---|---|---|---|---|
| 3 | **Actual Budget** | 29,275 | 100+（月更） | **MIT** | 本地优先 + 多端加密同步 | CRDT + E2E 加密 budget 文件 |
| 4 | **Actual Budget**（同上） | — | — | — | 银行同步 | GoCardless/SimpleFIN/PluggyAI 插件式 bank-sync |
| 5 | **Portfolio Performance** | 4,084 | 100+（6 周一版） | EPL-1.0 | 组合分析深度 | Classification 资产树 + TWR/IRR + 再平衡 + PDF 账单导入（20 年积累） |
| 6 | **OpenBB**（openbq-org/OpenBB） | 73,794 | 活跃（10-02 推送） | AGPL/自定义 | 金融数据接入标准化 | Router+Provider+统一 DataModel，20 家数据源一套 schema，MCP 一键暴露 |
| 7 | **TradingAgents** | 109,590 | 活跃 | Apache-2.0 | 多 agent 金融决策架构 | LangGraph：4 分析师并行 → bull/bear 辩论 → 风险辩论 → PM 裁决 |
| 8 | **ai-hedge-fund**（virattt） | 63,841 | 活跃 | MIT | agent 信号标准化 | persona=system prompt 子类 + 统一 Signal 接口 + ABSTAIN 弃权语义 |
| 9 | **FinRobot**（AI4Finance） | 8,129 | 活跃 | Apache-2.0 | 防 LLM 编数字 | 32 个确定性算子 + 6 个叙事审计算子（"数字出自代码，叙述出自 LLM"） |
| 10 | **midday-ai/midday** | 15,060 | **放缓**（0 commits/3mo） | AGPL-3.0 | 银行连接矩阵 | GoCardless/Plaid/Teller/EnableBanking 四 provider 抽象 + Magic Inbox（LLM 匹配票据→交易） |
| 11 | **rotki** | 4,040 | 100+ | AGPL-3.0 | 加密会计/税务 | SQLCipher 加密本地库 + 交易所连接器矩阵 + PnL 会计引擎 |

### 第三梯队：参考/借鉴价值

| # | 项目 | Stars | 活跃度 | License | 借鉴点 |
|---|---|---|---|---|---|
| 12 | Maybe Finance | 54,249 | **已归档**（2025-07） | AGPL-3.0 | Account/Entry/Valuation 单表多态模型（抄 schema 即可） |
| 13 | Firefly III | 24,806 | 100+（日更） | AGPL-3.0 | TransactionRule 规则引擎 + importer 凭证隔离；明确拒绝 AI |
| 14 | FinSight（RUC-NLPIR, ACL 2026） | 274 | 活跃 | — | Deep Research 流水线：搜索→验证→VLM 审图→分节成文 + Chain-of-Analysis 引用 |
| 15 | FinSight-AI（juanjuandog） | 1,061 | 活跃 | — | 报告绑定 dataSnapshotHash（数据变报告失效）+ evidence trace + RAG 回归评估 |
| 16 | Velora | 40 | **极活跃**（当日推送） | MIT | 个人版 daily brief 天花板：事实/推算/观点三色标签 + 推荐命中率统计 + "不行动是合法建议" |
| 17 | niuone | 315 | 活跃 | Apache-2.0 | LLM 起草、规则引擎执行；协议冻结 + 五阶段决策漏斗审计 |
| 18 | investorskills | 1,880 | 一般 | MIT | 投资判断资产化：SKILL.md/INVEST.md（YAML+散文双态，含 invalidation 条件与 sizing 上限） |
| 19 | Folo（RSSNext） | 39,054 | 活跃 | AGPL-3.0 | AI RSS 阅读器的信息流组织与 AI 整合 UX |
| 20 | newsnow | 21,945 | 活跃 | MIT | 多源新闻实时聚合的源抽象与性能 |
| 21 | Paisa | 3,220 | 低（单人） | AGPL-3.0 | ledger 文本记账 + 只读仪表盘（对 LLM 最友好的数据形态） |
| 22 | Finanze | 59 | 活跃早期 | AGPL-3.0 | 房地产 KPI 建模 + Python 版 GoCardless |
| 23 | LibreFolio | 20 | 高强度单人 | AGPL-3.0 | FX 转换路由图（多币种换算路径建模） |

（另有 rotki 已列第二梯队；Sossoldi 1,400★ MIT、Privatefolio 70★ 近停更、monetr 686★、MoneyManagerEx 2,271★ 档案见 research-notes，价值有限。）

## A3. 用户点名项目的核实结果

| 点名 | 核实结论 |
|---|---|
| Wealthfolio | ✅ 存在且极活跃，是"AI 财富 OS"最完整的开源参考实现 |
| Ghostfolio | ✅ 极活跃，数据模型与行情源抽象标杆 |
| **Finanze** | ✅ finanze/finanze（59★，非数百星项目）：Python+TS，GoCardless 同步 + 房地产 KPI，早期但活跃 |
| **LibreFolio** | ✅ Librefolio/LibreFolio（20★，2025-10 才建）：单人高强度开发，FX 路由图有想法，bus factor=1 |
| **FinSight** | ⚠️ 有两个：RUC-NLPIR/FinSight（ACL 2026 论文，Deep Research agent）与 juanjuandog/FinSight-AI（1k★ Java equity research），都值得借鉴 |
| **Privatefolio** | ⚠️ privatefolio/privatefolio（70★）：定位"配合 AI agent 使用的本地金融 toolkit"，但 2026-06 后近停更 |
| **astt** | ❌ 未找到任何匹配的金融项目（搜索 "astt finance" 零结果）。可能是记错的名字；若你想起全名可以再验证 |

## A4. 跨项目五条结构性发现

1. **"AI 财富管家"这个品类在开源界刚刚成型**：Wealthfolio（AI crate + MCP）、Privatefolio（为 agent 设计）、Velora（个人简报）都是 2025-2026 的产物，但没有任何一个同时做到「组合数据 × 情报摄取 × 教育 × 机会发现」的完整闭环——**这正是本产品的差异化空间**。
2. **AGPL 是这个领域的主导协议**（13 个追踪项目里 9 个）：fork 二次开发必须开源；MIT/Apache（Actual、ai-hedge-fund、TradingAgents、FinRobot、Velora）才能闭源复用。
3. **行情源没有免费午餐**：Yahoo/yfinance 是灰区且随时可能失效；所有成熟项目都做了 provider 抽象层（Ghostfolio 9 家、Wealthfolio 8 家、Portfolio Performance 10+）——这层必须自建。
4. **银行同步在亚太对个人不可行**（详见 research-notes/F），**券商 API 反而是突破口**（IBKR Flex Query / LongPort / Tiger 免费且免网关）。
5. **多 agent 金融系统的共识已经收敛**：数字出自代码、辩论式确认、证据链绑定数据版本、决策与执行分离、ABSTAIN 语义（详见 research-notes/C 的"8 条最佳实践"）。
