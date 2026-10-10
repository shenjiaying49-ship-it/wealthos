# H. Personalization Architecture — 个性化架构（Source Graph / Exposure / Profile）

**日期**：2026-10-03 · 对应用户第九、十、十六节

## H1. Personal Wealth Profile（用户画像，持续更新）

```yaml
# profile.yaml + 派生表，全部本地
identity:
  base_currency: HKD            # 用户自选（净值/简报的计价币）
  tax_residencies: [HK]         # 影响机会卡片的税务段
  jurisdictions_of_interest: [HK, SG, JP, US]   # 跨地区研究范围
income_expenses:                # 手动/CSV 导入，月度
  monthly_income: …; monthly_expenses: …; savings_rate: 派生
net_worth_series:               # 派生自 valuations
risk:
  capacity: 问答向导初始化（年限/目标/收入稳定性/负债）
  liquidity_needs: {emergency_months: 6, horizon_events: [{buy_house_2028, …}]}
goals: [{id: emergency_fund, target, deadline}, {id: house_downpayment, …}]
knowledge:                      # 引用教育域 knowledge_nodes（见 I 报告）
  known: [etf, compound_interest, diversification]
  learning: [bonds, duration]
  weak: [tax, derivatives, portfolio_construction]
preferences:
  brief_language: zh
  education_level: beginner
  risk_wording: conservative
```

更新机制：显式问答（onboarding 向导 + Chat 中的 `Questions For You`）+ 隐式推断（知识图谱来自测验结果；流动性需求来自大额支出模式）。**画像变更留版本历史**——brief 的"数据快照哈希"包含 profile 版本。

## H2. Financial Source Graph（金融信息宇宙的图谱）

### 实体类型与边

```
实体: CentralBank{Fed,ECB,BoJ,BoE,HKMA,MAS} | Currency | Country/Region
     | AssetClass | Sector | Company | ETF/Instrument | MacroConcept{利率,通胀,就业}
     | Institution{银行,券商} | Product{货币基金,T-Bill,定期存款} | MyAccount

边类型(edge_type + weight):
  central_bank_of(BoJ→JPY)           sets_policy_rate(BoJ→MacroConcept利率)
  affects(Fed利率→USD)               quoted_against(JPY↔USD)
  listed_in(7203.T→JP)               underlying(1321.T→Nikkei225→JP Equity)
  sector_of(AAPL→Tech)               currency_of(MyJPYCash→JPY)
  held_via(MyAccount→长桥)           carry_trade(JPY→GlobalRiskAppetite)  # 研究扩展
```

用户的例子（第九节）即一条图上路径：
`Bank of Japan → Interest Rate → JPY → Japanese Bonds/Stocks → Global Carry Trade → 我的 JPY Assets`

### 建图方式（务实：不追求通用知识图谱）

1. **种子图**：内置 ~200 实体/边的核心金融骨架（央行-货币-国家-资产类别层级 + 常见宏观传导边）——一次性人工整理 + LLM 辅助校对，随版本发布。
2. **持仓自动扩展**：导入持仓时自动把 `MyAccount×Instrument×Country×Currency` 挂进图（确定性代码）。
3. **新闻增量扩展**：News Agent 抽取的新实体/关系经 LLM 判分后**入候选边表**，人工或高置信阈值（>0.85）才转正——防止图谱被新闻噪声污染。
4. 边权语义：`0-1`，表示"对 A 的 1% 冲击传导到 B 的强度"，粗粒度即可（0.1/0.3/0.6/0.9 四档），供 relevance 排序用，**不做精确因果声明**。

### 图存储

SQLite 两张表（`entities` / `entity_edges`）+ 邻接查询足够（几百实体、几千边）；不引 Neo4j。查询模式固定两种：`exposure_paths(my_account → X)`（BFS ≤4 跳）与 `event_relevance(event.entity)`（反向查我的暴露路径）。

## H3. Exposure 引擎（每日重算，确定性代码）

```
exposures(as_of_date):
  currency:  {USD: 42%, HKD: 25%, JPY: 15%, CNY: 8%, …}      # 现金+证券币种+底层货币(ETF拆底层)
  country:   {US: 45%, JP: 18%, HK: 20%, …}                   # equity 按 issuer 国；ETF 按持仓拆
  sector:    {Tech: 30%, Financials: 12%, …}
  asset_class: {Equity 55%, Cash 30%, Bond 5%, Crypto 5%, RE 5%}
  institution: {IBKR: 40%, 长桥: 35%, 本地银行: 25%}
  single_symbol: top10 及其占比（>10% 标红）
```

- ETF 底层拆解：内置常见 ETF（VOO/2833.HK/1321.T…）的 region/sector 构成表（人工维护 50 只 + EODHD 可选补全）。
- 派生告警规则（Opportunity Agent 的输入）：现金 >40% 且无近期大额支出计划 / 单一机构 >50% / 单一币种 >60% / 单一标的 >10% / 债券 duration 与投资期限错配。

## H4. Portfolio-Aware News 的相关性计算

```
relevance(event) = Σ_paths  Π(edge_weight along path) × exposure_pct(路径终点)
                 × novelty(event_type 出现频率的倒数) × recency_decay

例: BoJ 加息
  path1: BoJ→JPY(0.9)→MyJPYCash(15%)         = 0.135
  path2: BoJ→JP Equity(0.8)→1321.T(10%)      = 0.080
  path3: BoJ→CarryTrade(0.3)→RiskAppetite(0.5)→MyEquity(55%) = 0.083
  → relevance ≈ 0.30 → 排入"与你有关"
```

输出解释模板（用户第十节，LLM 填充、代码供数）：
- What happened（仅 Fact 层，附官方链接）
- Why does it matter（Analysis 层，标注）
- Your exposure（来自 exposures 表的硬数字，代码生成）
- Possible implications（FX/Bond/Equity/Cash yield 四向，标注为推理）
- What to watch（后续事件日历）

## H5. 个性化输出契约

所有面向用户的输出强制三段元信息（Velora 三色标签的扩展）：
1. 每个数字后缀来源（`[计算]`/`[来源: FRED 2026-10-02]`）。
2. 每个论断前缀标签：`[事实]`/`[市场预期]`/`[分析]`/`[观点]`/`[AI 推断]`——五类不得混淆（用户第二十八节）。
3. 每个"与我有关"声明必须给出 exposure 依据（"你 15% 资产为 JPY 计价"），无依据的关联不上 brief。

禁止事项（用户第三十节，写进 system prompt + 审计算子双保险）：
- ❌ "你应该去香港开户" / "现在应该买黄金" / "Tesla 一定会涨" / "这是最好的配置"
- ✅ "基于你的情况，有几个值得研究的方案" + assumptions/evidence/risks/alternatives
