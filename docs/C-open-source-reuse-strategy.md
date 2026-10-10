# C. Open Source Reuse Strategy — 开源复用策略

**日期**：2026-10-03 · 决策依据：A/B 报告 + research-notes 全部 6 份调研

## C1. 总策略

**不 fork 任何大项目做基座，自建轻核心 + 库级集成 + 模式级借鉴。**

理由：
1. 候选基座全部是 AGPL（Ghostfolio/Wealthfolio），fork 后整个产品被迫 AGPL；且两者的核心价值（数据模型/行情抽象）抄思路的成本远低于维护一个 fork 的成本（Ghostfolio 100+ contributors 的代码库、Wealthfolio 的 Rust monorepo 都不是一个人能跟得动的）。
2. 本产品 70% 的价值在 AGPL 项目**没写**的部分（情报层/机会层/教育层/个性化）——基座越小，护城河占比越高。
3. 个人工具、单用户：不需要 Ghostfolio 的多用户/订阅/Premium 基础设施，不需要 Wealthfolio 的桌面打包与 Connect 商业层。

## C2. 分级清单

### Fork（仅 1 个，且是"必要时"）

| 项目 | 条件 | 用途 |
|---|---|---|
| ~~无~~ → **备用**：若后期想快速给家人朋友用 web 版，fork **Ghostfolio** 当只读展示层 | AGPL 兼容（我们核心也开源 AGPL 时） | 仅展示层，不承载逻辑 |

**实际推荐：Phase 1 零 fork。**

### Integrate（库级直接依赖）

| 依赖 | 用途 | License | 集成方式 |
|---|---|---|---|
| **yfinance** | 美股/ETF/日股/港股日线 + 盘中快照（低频+缓存+Stooq 兜底） | Apache-2.0 | pip |
| **Stooq**（非库，CSV API） | 日线兜底 + 港日全市场打包 | 免费 | 自写 provider |
| **frankfurter** | 汇率（可 Docker 自托管，本地优先） | MIT | HTTP |
| **FRED API** | 利率/美债/美国宏观 | 官方免费 | HTTP + 免费 key |
| **SEC EDGAR**（submissions/companyconcept/full-text） | 财报结构化数据 + filing 事件 | 公共领域 | HTTP（UA 合规） |
| **CoinGecko Demo** | 加密估值 | 免费 key | HTTP |
| **CCXT** | 交易所余额（可选） | MIT | pip |
| **quantstats** | 组合绩效报表（一键 HTML） | Apache-2.0 | pip（MVP 后期） |
| **PyPortfolioOpt** | 有效前沿/HRP 优化（What-if 模拟器） | MIT | pip（V2） |
| **pandas/numpy** | 计算层 | BSD | — |
| **feedparser + httpx** | RSS 摄取 | — | — |
| **LLM**：OpenAI/Anthropic SDK + 可选 Ollama | agent 大脑，BYOK | — | — |
| **MCP SDK**（python） | 把本地数据暴露给外部 agent（对齐 Wealthfolio/Ghostfolio 的新趋势） | — | V2 |

### Borrow（模式级借鉴——抄设计不抄代码）

| 来源 | 借什么 | 到哪里去 |
|---|---|---|
| **Ghostfolio** | Activity 枚举（BUY/SELL/DIVIDEND/FEE/INTEREST/LIABILITY）+ SymbolProfile 概念 + data-provider 抽象接口 | 数据模型 D + provider 层 |
| **Wealthfolio** | provider registry/resolver 模式；crates/ai 的 tool registry + BYOK 助手 | AI 架构 E |
| **Maybe** | Account/Entry/Valuation 单表多态（估值历史与交易统一） | 数据模型 D |
| **Actual Budget** | CRDT+E2E 同步（若未来多端）；bank-sync provider 接口形状 | 安全架构 L |
| **Portfolio Performance** | Classification 多层资产树 + 全谱系交易类型 + 再平衡计算 | 组合分析器 |
| **OpenBB** | Router+Provider+标准 DataModel 三分离；命令树自动导出 MCP 工具 | 数据网关架构 D/E |
| **TradingAgents** | bull/bear 辩论 + 独立裁决 + 报告头记录生成环境（模型/数据源/日期） | 机会发现 agent E |
| **ai-hedge-fund** | persona=system prompt 子类 + 统一 Signal 接口 + ABSTAIN 弃权 + prompt 缓存 | agent 标准化 E |
| **FinRobot** | "数字出自代码、叙述出自 LLM" + 叙事审计算子（发布前比对文本与数字） | Evidence Layer + 防"假确定性" |
| **FinSight-AI (juanjuandog)** | 报告绑定 dataSnapshotHash（数据变则报告失效）+ evidence trace | Evidence Layer |
| **FinSight (RUC)** | Deep Research 流水线：搜索→验证→成文 + Chain-of-Analysis 引用 | 财报 agent / 机会 agent 深研模式 |
| **Velora** | daily brief 的 [事实/推算/观点] 三色标签 + 推荐命中率统计 + "不行动是合法建议" | Daily Brief + Personal CFO 输出契约 |
| **niuone** | LLM 起草、规则引擎执行 + 决策漏斗留痕 + 协议冻结 | 决策/执行分离 |
| **investorskills** | 判断资产化格式（YAML+散文，含 invalidation/sizing 上限） | 教育 agent 的"投资哲学知识库" |
| **midday** | Magic Inbox（LLM+票据→交易匹配）、banking 4-provider 抽象（未来若做银行） | V2/V3 |
| **rotki** | SQLCipher 加密本地库实践 | 安全架构 L |
| **Folo/newsnow** | 多源信息流的"降噪→精选"UX | UI/UX K |

### Ignore（明确不用的）

| 项目 | 原因 |
|---|---|
| Firefly III / MoneyManagerEx / monetr / Sossoldi | 记账向，PHP/C++/Flutter 技术栈不匹配，功能被"手动 CSV + 规则引擎"覆盖 |
| rotki 整体 fork | 加密重仓特化；只借鉴加密存储 |
| Maybe | 已归档（2025-07），安全无人维护 |
| Privatefolio | 近停更（0 commits/3mo），只取"为 agent 设计"的定位灵感 |
| FinceptTerminal | NOASSERTION license + C++，终端定位不符 |
| FinGPT | 需自托管金融 LLM 才有意义；MVP 用 API LLM + 未来可选 |
| midday 整体 | 自托管全家桶（Supabase/Railway/Trigger.dev）对个人不现实 |

## C3. License 合规备忘

- 自建核心若开源 → 选 **AGPL-3.0**（与生态一致，防止云厂商白嫖）或 **MIT**（若想最大化传播）；本产品建议 AGPL。
- 引用 Apache/MIT 库（yfinance/quantstats/PyPortfolioOpt/CCXT）→ 无传染，闭源也行。
- 借鉴 AGPL 项目的**设计**（不复制代码）→ 合法；复制代码块 → 该文件 AGPL 传染，需标注。
- **数据**的 license 独立于代码：Yahoo 数据灰区（个人自用低风险）、Stooq 个人免费、EDGAR/FRED/央行公共领域、RSS 摘要+链接模式通行。

## C4. 一张图总结

```
自建核心（约 60% 工作量）           复用（约 40%）
┌────────────────────────┐      ┌─────────────────────────┐
│ 情报层 Pipeline         │      │ 行情/FX/汇率: yfinance+  │
│ Source Graph + Exposure │      │   Stooq+frankfurter     │
│ 机会发现引擎            │      │ 宏观: FRED+ECB+DBnomics │
│ 教育引擎 + 知识图谱      │      │ 财报: EDGAR XBRL        │
│ 9-agent 编排 + Evidence │      │ 新闻: RSS(CNBC/Fed/…)   │
│ Daily/Weekly/Monthly   │      │ 分析: pandas+quantstats │
│ UI (本地 web)           │      │ 优化: PyPortfolioOpt    │
│ SQLite schema + 导入器  │      │ LLM: OpenAI/Anthropic   │
└────────────────────────┘      └─────────────────────────┘
   抄思路: Ghostfolio模型/Wealthfolio AI架构/TradingAgents辩论/
           FinRobot审计算子/Velora三色标签/FinSight-AI快照哈希
```
