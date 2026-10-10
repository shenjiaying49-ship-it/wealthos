# I. Financial Education Architecture — 金融教育架构（Wealth Academy）

**日期**：2026-10-03 · 对应用户第十七~二十三节

## I1. 设计目标

"随着使用时间增加，我自己越来越懂钱"——教育引擎是产品的一等公民，不是附赠内容。三个特征：
1. **个性化**：课程由知识图谱缺口 × 用户真实资产 × 当周市场事件驱动。
2. **轻量**：每日一课 3-5 分钟，一个概念。
3. **闭环**：概念 → 关联我的资产 → 小问题 → 测验 → 图谱更新 → 影响下一课选择。

## I2. Financial Knowledge Graph（教育域）

```sql
knowledge_nodes(
  id, concept, domain,          # market_instrument/macro/accounting/risk/tax/behavior
  prereq_ids,                   # DAG: etf ← asset_class ← …
  importance,                   # 对"个人财富决策"的有用度 1-5
  status,                       # unknown/learning/known/weak
  mastery_score,                # 0-1，测验与复习更新
  last_reviewed)
```

**种子课程图谱（v1 内置 ~120 概念，覆盖 Day1-Day365）**：

| 域 | 示例概念（依赖序） |
|---|---|
| 基础 | 复利 → 通胀 → 购买力 → 风险与收益 → 流动性 |
| 工具 | 股票 → 债券 → ETF → 货币基金 → T-Bill → 定存 → 期权(可选) |
| 组合 | 资产配置 → 分散 → 再平衡 → 相关性 → 市值加权 |
| 债券进阶 | 久期 → 收益率曲线 → 信用利差 |
| 宏观 | 央行角色 → 政策利率 → 汇率机制 → 加息如何压估值 → carry trade |
| 账户/税务 | 券商类型 → 托管与 SIPC/投保 → CRS/FATCA 基础 → 各地账户特点 |
| 行为 | 损失厌恶 → 追涨杀跌 → 定投 → 市场择时的证据 |

## I3. 课程选择算法（每日一课）

```
score(concept) =
    gap_bonus        (status∈{unknown,learning,weak}: 3/2/2；known 复习到期: 1)
  × importance
  × relevance_bonus (与我的持仓/当周事件强相关: ×2)
  × prereq_ready    (前置已 known；否则先学前置)
  × anti_repeat     (近 14 天未出现)

pick = argmax(score)，且每周强制 ≥1 个"与我资产相关"概念、≥1 个图谱补洞概念
```

例：持有日股 ETF 且本周 BoJ 开会 → 本周课优先「政策利率如何影响你的日本 ETF（久期+汇率双通道）」。

## I4. Daily Lesson 格式（3-5 分钟，LLM 生成 + 模板约束 + 人工种子库优先）

```
📖 今日一课：什么是久期（Duration）？
1. 概念：2-3 句白话定义（≤150字）
2. 为什么重要：对"你的钱"意味着什么
3. 生活例子：房贷月供对利率的敏感度类比
4. 和我的资产的关系：〔代码注入〕"你的组合中债券敞口 X%，平均久期≈Y年，
   利率+1% → 价格约 -Y%（近似）"——真实数字来自 Portfolio Analyst
5. 一个小问题：单选，答对 mastery+，答错标记 weak
6. 延伸（可选）：本周相关的 1 条真实新闻链接
```

质量控制：种子课程（前 60 课）人工撰写存库，LLM 只做"个性化第 4 段"注入；LLM 生成新课时走 review 队列（生成→存草稿→次日用户可见前跑防错审计算子：数字是否与组合一致）。

## I5. Earnings 学习模式（用户第二十、二十一节）

持仓股财报日触发（Earnings Agent 联动）：
1. **Earnings Brief**（10 节固定格式：Revenue/EPS/GrossMargin/CashFlow/Guidance/Segment/管理层评论/What changed/What matters/How it relates to my portfolio）——前 7 节数字全部来自 EDGAR XBRL 代码计算。
2. **Learn From This Report**：本次财报挑一个指标做概念课（如 Gross Margin：是什么 → 为什么 Apple 的这个变化重要 → 在其他公司财报里怎么看），衔接知识图谱（brief 看完 → 概念 status: unknown→learning）。

## I6. Weekly Wealth Class（每周一堂）

- 内容源：本周市场主题（events 表聚合）+ 我的组合变化 + 用户近期薄弱概念。
- 结构：5 分钟课 + 1 个来自我组合的例子 + 1 张图（组合敞口/收益率曲线，代码出图，VLM/审计算子检查坐标轴与图例——FinSight 的 VLM 审图简化版）+ 3 个自测问题。
- 示例：「本周课程：为什么利率变化会影响股票估值？（以你的美股敞口为例）」

## I7. Monthly Financial Exam（Financial IQ Check）

- 5 题轻量测验（3 旧概念复习 + 2 新概念探测 + 1 情境题）。
- 输出：「你已理解 ETF 和复利，但对债券久期还不熟」→ 下月课程计划自动加权 duration 分支（图谱 status: known→weak 降级）。
- 复习调度：简化 SM-2（Anki 算法）——mastery 衰减 + 间隔复习。

## I8. 教育内容与 agent 的联动总结

```
Education Agent 输入:  knowledge_graph + exposures + events(本周) + quiz_history
Education Agent 输出:  daily_lesson / weekly_class / monthly_exam / curriculum_plan
下游消费:            Daily Brief 尾部"今日金融课" / Chat 中概念即问即答(RAG over 课程库)
反哺:                机会卡片可读知识状态 → 时机判断（用户不懂期权时不推结构性产品卡片）
```

最后一条是本架构的点睛：**教育状态反过来约束机会推荐的复杂度**——一个不懂久期的人不应收到"债券阶梯"卡片，应先收到久期课。这让"教育"与"建议"形成负责任的闭环，正是"AI 替我做研究，我负责决策"理念的落地。
