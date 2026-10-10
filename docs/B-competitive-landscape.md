# B. Competitive Landscape — 竞争格局分析

**日期**：2026-10-03 · 依据：A 报告的 23 个开源项目调研 + 数据源实测

## B1. 市场地图：谁在解决什么

```
                个人理财工具光谱（按"离钱远近 × 智能程度"）

纯记录 ──────────────── 分析 ──────────────── 洞察/建议
  │                        │                        │
MoneyManagerEx         Portfolio Performance     （空旷地带）
Firefly III            Ghostfolio                 ← 目标用户真正需要的：
Actual Budget          Wealthfolio                   "告诉我哪些财富选择值得考虑"
Sossoldi               rotki                        没有开源产品在做
                       Maybe(已归档)
```

### 现有产品解决的四个问题

| 问题 | 已被谁解决 | 成熟度 |
|---|---|---|
| **记账/预算**（钱花哪了） | Actual、Firefly III、MoneyManagerEx | ★★★★★（20 年成熟，无创新空间） |
| **组合追踪**（我有多少钱、收益如何） | Ghostfolio、Wealthfolio、Portfolio Performance | ★★★★（数据模型已收敛，多币种/TWR/再平衡都是解过的题） |
| **投研终端**（市场发生了什么） | OpenBB、FinceptTerminal（32k★）、TradingAgents | ★★★☆（面向交易员/量化，不是面向"理财意识弱的普通人"） |
| **AI 研究 agent**（怎么研究一家公司） | ai-hedge-fund、FinRobot、FinSight | ★★☆（学术/演示向，不接个人真实数据） |

### 没有被任何产品解决的问题（本产品的定位）

1. **Portfolio-Aware News**：Ghostfolio/Wealthfolio 完全不做新闻；OpenBB/TradingAgents 完全不接个人数据。"这条新闻与我的 JPY 敞口有什么关系"——两头都是空白。
2. **Financial Education Engine**：没有任何开源产品有"知识图谱 + 每日一课 + 月度测验"的财富教育闭环。投资者教育内容散落在 YouTube/Newsletter 里。
3. **Opportunity Detection（非荐股向）**：现有 AI agent 全部在做"该买什么股票"（ai-hedge-fund/TradingAgents），没有人做"你该研究香港多币种账户吗/现金放货基还是 T-Bill"这类**现金与账户结构层面的机会发现**。
4. **Signal ≠ Truth 的验证层**：X 情报 → 官方源确认 → 可信度分级，这条管线没有现成实现。

## B2. 按用户核心诉求逐条对照

用户 8 个诉求 × 现有最优解 × 空缺：

| 用户诉求 | 现有最优开源方案 | 空缺程度 |
|---|---|---|
| 看钱（净值/账户） | Wealthfolio / Ghostfolio | 已解决，直接复用 |
| 看市场（行情/宏观） | OpenBB + FRED + 自建 provider | 数据可得，需自建编排 |
| 看机会（账户/配置优化） | **无** | 完全空白，自建 |
| 看风险（敞口/集中度） | Ghostfolio X-Ray（浅）+ Portfolio Performance（深但手动） | 半空缺 |
| 看账户（结构优化） | **无**（连商业产品都很少做） | 完全空白，自建 |
| 看全球（跨地区金融体系研究） | **无** | 完全空白，自建 |
| 看公司（持仓股财报解读） | FinSight/FinRobot（不接个人数据） | 半空缺 |
| 学金融（教育引擎） | **无** | 完全空白，自建 |

**结论**：8 个诉求里 2 个已被优秀开源项目解决（复用），3 个半空缺（借架子自建），3 个完全空白（原创，也是产品护城河）。

## B3. 商业产品对照（非 fork 但定义了用户体验基准）

| 产品 | 它教给我们什么 |
|---|---|
| **Copilot Money / Monarch** | "净值的日常叙事化"——每天用一句话解释你的钱的变化，这是 Daily Brief 的体验基准 |
| **Kubera** | 跨资产（含房产/加密）净值追踪 + 每类资产的"如果卖掉要交多少税"视角；$150/年证明这人群付费意愿 |
| **Delta / Ghostfolio Cloud** | 桌面组合追踪的商业化上限 |
| **Perplexity Finance / Rogo** | AI 金融研究的交互范式：追问、引用、免责声明 |
| **Feedly / Folo** | AI 阅读器的"噪音过滤→每日 3-5 条"体验基准 |
| **Ramsey/ dodowell / 收益率 App（国内）** | 教育型内容产品化的先例，但都不是个性化的 |

## B4. 竞争结论

1. **不要与 Ghostfolio/Wealthfolio 竞争组合追踪**——直接站在它们肩上（fork 或集成），把自建资源全部投入它们不做的三层：情报层（Portfolio-Aware News）、机会层（Options Engine）、教育层（Academy）。
2. **不要与 OpenBB 竞争数据平台**——用它的 Provider 思想但自己维护轻量版（个人工具不需要 20 家 provider，8-10 个够）。
3. **差异化定位一句话**：*"Ghostfolio 记录你的钱，TradingAgents 研究市场，但没有人把你*的钱*和*市场*连起来讲给你听，还顺便教你金融。"* 这是产品愿景里"帮助没有理财意识的人拥有专业财富管理团队的信息能力"的直接翻译。
4. **护城河排序**：个性化（我的真实敞口 × 全球信息的 join）> 教育闭环（知识图谱随使用积累）> 证据层（每条结论可溯源）。三者都是数据/时间累积型，后来者难以速成。
