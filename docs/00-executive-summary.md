# AI Personal Wealth Intelligence OS — 第一阶段调研与设计交付（执行摘要）

**日期**：2026-10-03 · 状态：Research First 完成，可进入 Phase 0

## 交付物清单

| 文档 | 内容 | 关键结论 |
|---|---|---|
| **A. GitHub Research** | 23 个开源项目深度调研（元数据全部当日实测） | Wealthfolio/Ghostfolio 是唯二"AI 财富管家"直接竞品；用户点名项目全部核实（"astt"未找到） |
| **B. Competitive Landscape** | 竞争格局与空白分析 | 8 个核心诉求中 3 个完全空白（机会发现/账户优化/教育闭环）——即本产品定位 |
| **C. Reuse Strategy** | Fork/Integrate/Borrow/Ignore 四级策略 | **零 fork 自建轻核心**；库级复用 12+；模式级借鉴 15 项 |
| **D. Data Architecture** | SQLite 三层数据架构 + provider 抽象 | 快照+事件双轨；yfinance+Stooq 主备；多币种一等公民 |
| **E. Agent Architecture** | 9 agent + 审计器的 Hub-and-Spoke | 摄取与分析分离；辩论式机会确认；ABSTAIN 语义 |
| **F+G. 信息源与摄取** | 分层源清单（全部实测）+ 八步管线 | 官方 RSS + EDGAR 是零成本基石；Reuters RSS 已死/X API 转 PPU |
| **H. Personalization** | Source Graph + Exposure 引擎 + 画像 | relevance = 图路径 × 敞口权重，Portfolio-Aware News 的实现基础 |
| **I. Education** | 知识图谱 + 每日一课 + 测验闭环 | 60 课种子；教育状态反哺机会推荐的复杂度门 |
| **J. MVP Spec** | 8 周 10 个 Must 功能 + 验收脚本 | 端到端验收：导入真实数据→次日晨报可信可溯源 |
| **K. UI/UX** | 6 页 IA + Today 页详设 | "读的 newsletter"而非仪表盘；证据抽屉/五类标签贯穿 |
| **L. Security** | 威胁模型 7 项对策 | keychain 全托管；Privacy Filter 三层脱敏；只读三重防线 |
| **M. Roadmap** | 0→1→2→3 四阶段 29 周 | 每阶段可独立使用；MVP 月成本 $10-30（可归零） |
| research-notes/（6 份） | 数据源/追踪项目/Agent 框架/X 合规/新闻财报/银行券商 API 原始调研 | 全部带 URL 与实测证据 |

## 五个最重要的调研发现

1. **开源界没有完成品**：Wealthfolio（AI crate+MCP）和 Ghostfolio（MCP endpoint）2026 年都在向"AI 化"演进，但都只到"AI 能读我的数据"为止——"AI 替我持续研究全球信息并翻译成我的机会"这一层没有任何项目做。产品愿景成立且不撞车。

2. **X 的合规答案比预想好**：X API 已转向按用量付费（2026-02 起），只读 List 轮询 $0.005/条、24h 去重计费，小规模跟踪 $5-30/月（比旧 $200 Basic 便宜一个量级）；Nitter 已死、灰色路径全部排除；Substack RSS + Fed/SEC 官方 feed 构成零成本替代底座。

3. **银行同步在亚太结构性不可行，券商 API 是突破口**：GoCardless 已关新注册、HKMA/SGFinDex 机构准入、日本无个人 API；但 IBKR Flex Query（免费、免网关、天生只读）+ LongPort/Tiger（云端直连）完整覆盖港美日券商场景。

4. **多 agent 金融系统最佳实践已收敛**（TradingAgents 10.9 万★等项目的共识）：数字出自代码叙述出自 LLM、统一数据契约、ABSTAIN 弃权、辩论式确认、报告绑定数据快照哈希、决策与执行分离、判断资产化、自我问责。本架构全部吸收。

5. **免费数据栈完全够 MVP**：行情（yfinance+Stooq）/汇率（frankfurter）/利率（FRED+Treasury）/宏观（ECB/BoE/DBnomics/IMF/WB/OECD 全无 key）/财报（EDGAR XBRL + Motley Fool transcripts + Nasdaq 日历）——$0 起步，付费升级位（EODHD $20/月）随时可切。

## 建议的下一步

按 M3 行动清单执行 Phase 0（本周）：建 repo、冻结 D3 schema、导入第一批真实数据、跑通"手动触发一次 Collect→Brief"。第一个端到端 demo 的标准：终端里打印出一份每个数字都带来源的晨报。
