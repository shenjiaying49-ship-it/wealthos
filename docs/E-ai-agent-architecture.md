# E. AI Agent Architecture — AI Agent 架构

**日期**：2026-10-03 · 依据：research-notes/C（10 个 AI 金融框架的 8 条最佳实践）+ B/D 报告

## E1. 总体拓扑：Hub-and-Spoke，不做自由聊天群

```
                        ┌────────────────────────┐
                        │   Personal CFO Agent    │   ← 唯一面向用户的综合层
                        │  (orchestrator + 编辑)  │
                        └───────────┬────────────┘
        ┌──────────┬───────────┬───┴──────┬───────────┬──────────┐
        ↓          ↓           ↓          ↓           ↓          ↓
   Portfolio    Opportunity  Education  Daily Brief  Chat       Evidence
   Analyst      Agent        Agent      Composer    (RAG)       Auditor
   (分析)        (机会发现)   (教育)      (简报合成)   (问答)      (审计,无LLM?)
        ↑          ↑           ↑          ↑           ↑
        └──────────┴───────────┴──────────┴───────────┘
                            ↓ 只读
        ┌─────────────────────────────────────────────────┐
        │        Data Gateway (统一工具层, MCP 化)          │
        │  market.*/portfolio.*/news.*/earnings.*/graph.*  │
        └─────────────────────────────────────────────────┘
                            ↑
        ┌──────────┬───────────┬──────────┬──────────┐
        │ Financial│ Market    │ X Intel  │ News     │  ← 摄取层 worker（无 LLM 或
        │ Data     │ Macro     │ Agent    │ Agent    │    仅用小模型做分类/摘要）
        │ Agent    │ Agent     │ (可选层)  │ Earnings │
        └──────────┴───────────┴──────────┴──────────┘
```

关键决策（源自调研的 8 条最佳实践）：
1. **摄取与分析分离**：下面 4 个"agent"其实是确定性 worker（Collect→Filter→Classify），LLM 只在分析/解释层出现——数字出自代码，叙述出自 LLM（FinRobot 原则）。
2. **统一 Data Gateway**：所有 agent 通过同一个工具层读数据（OpenBB Router 模式），工具即函数，自动生成 MCP schema——未来外部 agent（Claude Code 等）可直接接入本地财富数据（对齐 Wealthfolio/Ghostfolio 的 MCP 新趋势）。
3. **编排用代码不用框架**：不引 LangGraph/CrewAI（TradingAgents 10 万★也只是在 LangGraph 上搭图；个人工具用 Python 函数 + 显式 pipeline 更可控、可调试）。LLM 调用统一走一个 `llm.py`（支持 OpenAI/Anthropic/Ollama，BYOK，含 prompt/response 持久化与缓存——ai-hedge-fund 的 PromptCache 模式）。

## E2. 九个 Agent 的规格

### 1. Financial Data Agent（确定性 worker，无 LLM）
- 职责：账户同步（CSV/Flex/长桥/IBKR）、导入校验（D6 数据质量规则）、快照生成、净值/汇率落库。
- 输出：`valuations` / `activities` / 校验告警。

### 2. Market Agent（确定性 + 小模型标注）
- 职责：行情/FX/利率/宏观定时拉取（D4 provider 链）；宏观事件规范化（FOMC 日期→`events` 表）。
- LLM 用途（可选小模型）：给宏观数据变化生成一句话客观描述（禁止预测）。

### 3. X Intelligence Agent（可选插件层）
- 职责：X API PPU List timeline 轮询（BYOK，$0.005/条，24h 去重计费对齐缓存窗口）；来源分级（Official/Professional/Research/Journalist/Analyst/Individual/Anonymous）；可靠性标注（Primary/High/Medium/Low/Unverified）。
- **Signal ≠ Truth**：输出只是 `signals` 表里的信号，进 News Agent 的验证队列，永不直接进 brief。
- 默认关闭，无 key 时降级为 RSS/Newsletter 情报（Substack feed 等）。

### 4. News Agent（LLM 轻量分类 + 验证）
- 职责：RSS/官方源摄取 → 去重（canonical URL → simhash → 事件键三级）→ 事件归并 → **与 Source Graph join 打相关性分** → 分级：`与我有关 / 值得知道 / 噪音`。
- 验证管线（用户第七节要求）：`X signal/新闻声称 → 找原始来源（EDGAR/Fed/央行/权威媒体）→ 确认或标注未确认`。输出区分：Fact / Market Expectation / Analysis / Opinion / AI Inference 五类标签（Velora 三色标签的扩展版）。

### 5. Earnings Agent（深研模式，借鉴 FinSight pipeline）
- 触发：持仓股财报日（Nasdaq calendar + EDGAR 8-K 确认）。
- 流程：EDGAR XBRL 拉结构化指标（Revenue/EPS/GrossMargin/现金流，companyconcept 带 tag 回退列表）→ 代码计算 YoY/QoQ/预期差 → Motley Fool transcript 拉取 → LLM 生成 10 节 Earnings Brief（用户第二十节的格式）→ 每个数字带来源引用。
- 教育联动：brief 里嵌一个"本课概念"（如 Gross Margin），由 Education Agent 提供。

### 6. Portfolio Analyst（确定性计算 + LLM 叙述）
- 确定性部分（代码）：多币种净值、TWR/MWR、exposures 五维（币种/国家/行业/机构/单一标的）、集中度告警、与再平衡目标偏差、情景模拟器（What-if：现金流/波动率/流动性/汇率敞口，PyPortfolioOpt + 蒙特卡洛）。
- LLM 部分：把计算结果翻译成人话 + 指出 3 个最值得注意的点（输入是结构化结果 JSON，不是原始数据——防编数）。

### 7. Opportunity Agent（辩论确认制，借鉴 TradingAgents/FinRobot）
- 触发：规则扫描（现金占比过高/单券商集中/单一币种敞口/新宏观环境变化）+ Education Agent 的知识缺口。
- 流程：`候选生成（规则+LLM）→ bull/bear 各一轮互驳（注入对方论点）→ 裁决（强模型）→ 输出 Opportunity 卡片`。
- Opportunity 卡片结构 = 用户第十一节模板：为什么值得研究/解决什么问题/适合什么情况/主要成本/开户要求/税务合规/货币风险/流动性/替代方案/目前是否符合/建议进一步研究。
- 硬护栏：永不输出"你应该 X"；每张卡带 invalidation 条件与 sizing 上限字段（investorskills 格式）。

### 8. Education Agent（详见 I 报告）
- 职责：知识图谱维护 → 课程选择（依赖缺口 + 当周市场事件 + 用户资产）→ 生成 3-5 分钟 Daily Lesson → 周课/月考编排。

### 9. Personal CFO Agent（唯一综合层）
- 输入：以上所有 agent 的**结构化输出**（不是原始数据）。
- 职责：编排 Daily/Weekly/Monthly brief（用户第二十四~二十六节的三套模板）；Chat 模式的总入口（RAG over reports/items/lessons）；统一输出契约（用户第二十九节：Situation/Exposure/Why/Options/Benefits/Risks/Costs/Liquidity/Tax/Unknowns/Questions For You）。
- 记忆：历史 brief 注入防复读（只讲增量，Velora 模式）；用户纠错/偏好记入 profile。

### 横切：Evidence Auditor（确定性代码，无 LLM）
- 发布前检查（FinRobot 叙事审计算子的轻量版）：brief 里出现的每个数字能否在 `计算结果 JSON` 里找到；五类标签是否都标了；引用链接是否真实存在；数据快照哈希绑定（FinSight-AI 模式：`data_snapshot_hash` 变了报告自动失效重生成）。

## E3. LLM 策略

| 场景 | 模型档位 | 频次 | 预估月成本（API 计价） |
|---|---|---|---|
| 新闻分类/打分 | 小模型（Haiku/4o-mini/本地 Ollama） | 每日 100-300 条 | $1-5 |
| Earnings Brief | 中档 | 每持仓股每季 1 次 | 忽略不计 |
| 机会辩论 + 裁决 | 强模型（仅裁决用强） | 每周几次 | $2-10 |
| Daily Brief 合成 | 中-强 | 每日 1 次 | $3-15 |
| Chat | 用户交互按需 | — | 按使用 |
| **合计** | | | **约 $10-30/月**（BYOK，可切 Ollama 降至 $0） |

缓存与幂等：相同输入（data_snapshot_hash 相同）绝不重复调用；prompt/response 全部落 `llm_calls` 表可审计。

## E4. 失败语义（对齐 ai-hedge-fund）

- 数据层失败 → **fail loud**：brief 里明写"今日行情数据缺失，净值未更新"，绝不静默用昨日数据冒充。
- LLM 失败/解析失败 → **ABSTAIN**：该条目降级为"未经 AI 分析的原始条目"，不编造。
- 一切 AI 输出默认带 `confidence` 与 `evidence[]`；无 evidence 的结论不许出现在 brief 正文（只能进"未验证信号"区）。
