# J. MVP Specification — V1 最小可行产品规格

**日期**：2026-10-03 · 范围对齐用户第三十二节，砍到"一条腿能跑通闭环"的最小集

## J1. MVP 目标与验收标准

**目标**：8 周内做到——每天早上打开，看到一份"与我有关的"晨报，且其中每个数字可信、每条结论可溯源、组合数据是真实导入的。

**验收场景（端到端 demo 脚本）**：
1. 导入 IBKR Flex XML + 2 个 CSV（本地银行现金 + 长桥持仓），10 分钟内得到多币种净值与五维敞口。
2. 次日 07:00，Daily Brief 生成：净值涨跌、3 条值得知道的新闻（其中 ≥1 条与持仓相关且带敞口解释）、1 张机会卡片、1 节 3 分钟课程。
3. 点开任何数字能看到来源与计算式；点开任何新闻能看到证据链与五类标签。
4. Chat 里问"我现在的日元风险大吗"，得到基于 exposures 的回答并引用当日汇率。

## J2. 技术栈（决策）

| 层 | 选型 | 理由 |
|---|---|---|
| 语言 | **Python 3.12+** | 数据/金融生态（yfinance/pandas/PyPortfolioOpt）+ LLM SDK；单人可维护 |
| 存储 | SQLite（WAL）+ sqlite-vec | 本地优先；见 D 报告 |
| 后端 | FastAPI + APScheduler | 轻量；摄取调度与 API 同进程 |
| 前端 | **本地 web：Next.js(或 Vite+React) + Tailwind**，浏览器打开 localhost | 比 Tauri 打包快得多；桌面化留 V2（对齐 Wealthfolio 路径） |
| LLM | OpenAI/Anthropic API（BYOK）+ 预留 Ollama | 见 E3 成本表 |
| 通知 | 界面内 + （可选）macOS terminal-notifier | Telegram bot 留 V1.5 |

## J3. 功能清单（MoSCoW）

### Must（MVP 核心，缺一不可）

| # | 功能 | 规格摘要 |
|---|---|---|
| M1 | 账户/持仓导入 | IBKR Flex XML 解析器 + 通用 CSV 映射向导（列映射记忆）+ 手动录入；导入校验（D6 规则） |
| M2 | 净值与敞口仪表盘 | 多币种净值曲线（历史汇率换算）、五维 exposures 环形图/条形图、top10 单一标的 |
| M3 | 行情/FX/利率摄取 | yfinance+Stooq provider 链、frankfurter 汇率、FRED 利率；每日收盘后批处理 + stale 标记 |
| M4 | 新闻摄取 L0+L1 | 官方 RSS（Fed/ECB/EDGAR）+ CNBC/SA ticker/GNews RSS；三级去重；事件归并 |
| M5 | 相关性引擎 | 种子 Source Graph + exposures join → relevance 排序（H4 公式） |
| M6 | **Daily Brief** | 用户第二十四节模板；三-五条新闻 + 一件与我有关 + 一张机会卡 + 今日课；data_snapshot_hash 绑定；五类标签 |
| M7 | Evidence Layer | 每条结论 evidence[]（url+日期+来源）；数字→计算式/数据源弹层；审计器（数字核对）跑在发布前 |
| M8 | AI Chat | RAG over（组合快照+events+items+课程）；输出契约（第二十九节 11 段式，投资相关时强制） |
| M9 | 教育引擎 v1 | 内置 60 课种子课程 + 每日一课 + 小问题；知识图谱 status 流转 |
| M10 | 财报 Brief v1 | 持仓美股财报日自动生成（EDGAR XBRL 指标 + 10 节格式 + 1 个学习概念） |

### Should（MVP 加分，时间允许）

- What-if 模拟器 v0（现金→债券的收益/波动/流动性三指标静态对比表）
- 周报 Weekly Brief（用户第二十五节模板，聚合 daily 数据，代码为主 LLM 为辅）
- X 层插件位（设置页留 BYOK 入口，接通即用 List 轮询）
- 机会卡片 v1（3 类规则触发：现金占比/机构集中/币种集中；不接辩论，标记"v2 升级"）

### Could / Won't（明确不做）

- ❌ 银行自动同步（research-notes/F：亚太不可行）→ 永久 CSV
- ❌ 券商 API 自动同步（IBKR Flex 自动拉取放 V2；MVP 手动下载文件够用）
- ❌ 移动端 App / 多用户 / 加密同步（V3）
- ❌ 自动交易、订单、价格告警（产品定位外）
- ❌ 自托管金融 LLM（FinGPT 路线，成本/收益不匹配个人工具）

## J4. 关键页面（与 K 报告对应）

1. `Today`（Daily Brief 阅读）2. `Portfolio`（净值/敞口/持仓表）3. `Feed`（新闻流，按相关性/时间切换，含证据抽屉）4. `Learn`（今日课/课程库/图谱进度）5. `Research`（财报 brief 存档）6. `Settings`（数据源/LLM key/导入）

## J5. MVP 数据源配置（零成本启动）

```yaml
quotes:   [yfinance(12h缓存), stooq(fallback)]
fx:       frankfurter
rates:    FRED(key=用户免费申请) / treasury fiscaldata(无key)
news:     [fed_rss, ecb_rss, edgar, cnbc, seekingalpha_ticker, google_news]
calendar: nasdaq_earnings
crypto:   coingecko_demo(可选)
llm:      user_byok (openai 或 anthropic 二选一即可跑通)
```

## J6. MVP 里程碑（8 周）

| 周 | 交付 |
|---|---|
| 1-2 | SQLite schema + 导入器（Flex/CSV）+ 净值/敞口计算 + Portfolio 页只读 |
| 3 | 行情/FX/利率 provider 链 + 调度 + stale 处理 |
| 4 | 新闻摄取 + 去重 + 事件模型 + 种子 Source Graph + relevance |
| 5 | LLM 层（llm.py 缓存/审计）+ Daily Brief v1 + 五类标签 + Evidence 弹层 |
| 6 | 教育 v1（60 课种子 + 流程）+ Chat RAG |
| 7 | 财报 Brief + 周报 + What-if v0 + 机会卡 v1 |
| 8 | 打磨：审计器覆盖、错误态、onboarding 向导、真实数据两周试跑与修 bug |

## J7. 风险与对策

| 风险 | 对策 |
|---|---|
| yfinance 被封 | Stooq 兜底已内置；极端情况切换 EODHD（$20/月，配置即用） |
| LLM 月费超预期 | 小模型跑分类；Ollama 本地降级路径；llm_calls 表做用量看板 |
| 新闻噪声过高 | 阈值初值保守（只报 relevance>0.15），白名单/黑名单 UI 一键反馈 |
| 单人开发烂尾 | 见 M 报告"每周可发布"节奏；MVP 砍到 M1-M10 不扩张 |
| 个人数据安全 | 见 L 报告（本地、无云、key 进 keychain） |
