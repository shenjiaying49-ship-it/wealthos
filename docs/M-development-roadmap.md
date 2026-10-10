# M. Development Roadmap — 开发路线图

**日期**：2026-10-03 · 节奏原则：每阶段结束都有"可每天使用"的产出（防单人烂尾）

## M0. 阶段总览

```
Phase 0  准备        (1 周)     → 仓库/骨架/数据模型冻结
Phase 1  MVP         (8 周)     → 每天一份可信的晨报（J 报告 M1-M10）
Phase 2  深化        (+8 周)    → 自动同步/模拟器/辩论级机会引擎/X插件
Phase 3  Wealth OS   (+12 周)   → 跨地区研究引擎/多端/桌面化
```

## Phase 0（第 1 周）：地基

| 任务 | 产出 |
|---|---|
| repo 初始化（Python + uv + SQLite + FastAPI 骨架 + 前端脚手架） | CI 跑通 |
| D3 schema 建库 + 种子数据（Source Graph 骨架 200 实体） | `schema.sql` + seed |
| 导入自己真实数据（Flex + CSV）验证模型 | 我的真实净值第一版 |
| FRED/LLM key 申请与 keychain 集成 | settings 页可用 |

## Phase 1（第 2-9 周）：MVP（详见 J6 周计划）

里程碑门（第 9 周末验收）：
- [ ] 连续 14 天 Daily Brief 无人工干预生成
- [ ] 审计器拦截率（数字无源/标签缺失）= 100% 处理
- [ ] 我本人每天真的会打开看（dogfood 标准高于一切）
- [ ] LLM 月账单 < $30

## Phase 2（第 10-17 周）：深化（用户第三十三节 V2）

| 周 | 主题 | 内容 |
|---|---|---|
| 10-11 | **自动同步** | IBKR Flex Query 自动拉取（token 一次性配置）；LongPort OpenAPI 接入（云端直连最轻）；connector 网络白名单 |
| 12 | **多币种现金管理** | 现金分层视图（活期/定存/货基/T-Bill），利率对比表（FRED+各行官网人工维护小表） |
| 13-14 | **What-if 模拟器完整版** | PyPortfolioOpt 有效前沿 + 蒙特卡洛 + 目标情景（"两年后买房"→应急金/久期/风险容量重排） |
| 15 | **机会引擎 v2** | 接入 bull/bear 辩论 + 裁决；机会卡片全 11 字段；机会→课程的复杂度门（I8） |
| 16 | **X 情报插件** | X API PPU BYOK 接入（List 轮询 + since_id 增量 + 24h 去重缓存 + 消费熔断）；来源分级与可靠性标注 |
| 17 | **风险监控 + 告警** | 敞口阈值/集中度/流动性覆盖率监控；事件驱动提醒（FOMC/财报日/大额变动） |

## Phase 3（第 18-29 周）：AI Wealth OS（用户第三十四节 V3）

| 主题 | 内容 |
|---|---|
| **跨地区研究引擎** | HK/SG/JP/US 四地区金融体系知识库（账户类型/券商/税务/合规结构化），生成用户第十二、十三节格式的地区对比报告；不默认推荐任何地区（第十四节原则） |
| **Financial Options Engine 完整版** | banking/brokerage/cash_mgmt/diversification 四类机会的持续扫描 + 每季"账户结构体检"报告 |
| **月度 Wealth Review** | 净值轨迹归因（收入/储蓄/市值/FX 四分解）、知识回顾、下月关注（用户第二十六节） |
| **桌面化与多端** | Tauri 打包（mac/win）或保留 web + Actual 式 E2E 同步（二选一，看 dogfood 需求） |
| **MCP server 对外** | 本地数据/工具树暴露为 MCP（对齐 Wealthfolio/Ghostfolio 趋势）——任意 AI agent 可安全读我的财富数据 |
| **教育内容扩展** | 种子课 60→120+；Monthly Exam 自适应；真实财报学习库积累 |

## M1. 资源与成本预算

| 项 | Phase 1 | Phase 2+ |
|---|---|---|
| LLM API | $10-30/月 | 同左（+Ollama 可归零） |
| 数据源 | $0 | 可选 EODHD $20/月；X 层 $5-30/月 |
| 基础设施 | $0（本机） | $0-5（若用 VPS 拉取） |
| 人力 | 单人业余时间，每周 ≥10h 维持节奏 | |

## M2. 风险登记册（Top 5）

| 风险 | 概率 | 缓解 |
|---|---|---|
| 单人开发节奏中断 | 高 | 每周可发布原则；Phase 1 后任何时点停做都是"可用产品"而非半成品 |
| yfinance 失效 | 中 | Stooq/EODHD 双兜底已设计（D4） |
| LLM 用语失误（假确定性） | 中 | 三层防线：system prompt 禁令 + 审计算子 + 输出契约（H5） |
| 维护疲劳（源太多） | 中 | 源按 tier 分级淘汰：连续 30 天 relevance=0 的源自动降权提示移除 |
| X API 再变价 | 中 | X 层是可选插件（research-notes/D 结论），核心功能零依赖 |

## M3. 立即行动清单（本周可做）

1. 建 repo + Phase 0 四任务（半天可完成骨架）；
2. 申请 FRED key + 选定 LLM 供应商（各 10 分钟）；
3. 从券商导出第一份 Flex 报告/CSV 投入 `inbox/`；
4. 把 research-notes/E 的 RSS 清单复制为初始 `sources.yaml`（15 分钟）；
5. 跑通第一个 E2E：手动触发一次"Collect→Brief"流水线（即使 UI 未完成，终端输出 brief 文本即算成功）。
