# X/Twitter 金融信息合法获取路径合规调研报告

**调研日期**：2026-10-03 | **用途**：个人自用 AI 财富管理工具的情报层设计 | **原则**：只评估合规路径，明确标注灰色路径为不推荐

---

## 一、X 官方 API 现状（2026）：已彻底转向按用量付费（Pay-Per-Use）

### 1.1 重大变化：订阅档位已死，信用点模式当道

2026 年 X API 完成了定价模型革命，这是本次调研最重要的发现：

| 事件 | 时间 | 说明 |
|---|---|---|
| PPU 模式官宣 | 2026-02 | 放弃 $200/$5,000 固定月费，转向按用量计费（Gigazine, 2026-02-09） |
| **Free 档对新项目关闭** | **2026-02-06** | 此前 Free 档仅允许写（500 条/月），无读取权限 |
| **Basic $200 强制迁移 PPU** | **2026-06-01** | 不可逆（devcommunity.x.com，2026-04/06 讨论） |
| Legacy Pro 迁移 PPU | 2026-08 | 官方公告 "Legacy X API Pro Plans Are Moving to Pay-Per-Use" |
| Nitter 收到停止函 | 2026-08-24 | 见第三节 |

### 1.2 现行官方价格（来源：docs.x.com/x-api/getting-started/pricing，2026-10-03 抓取）

**读取类**（按返回资源计费）：
- Post 读取：**$0.005/条**
- User 读取：$0.010/个
- **List 读取：$0.005/条**（List timeline 可用）
- 自己账号的数据（如 `GET /2/users/{id}/tweets` 查自己）：$0.001/条

**关键机制**：
- 无订阅、无合同、无最低消费；预充值信用点，Developer Console（console.x.com）管理
- **24 小时去重**：同一资源 24h 内重复请求只计费一次（"soft guarantee"）——这对轮询架构非常有利
- **月度上限：300 万条 Post 读取**，超出需 Enterprise
- 首次绑卡送 $20 信用点；累计消费 $200+ 送 10–20% xAI 信用点返奖
- 支持自动充值与消费上限设置

**Rate limit**（与计费独立，来源：docs.x.com/x-api/fundamentals/rate-limits）：
- `GET /2/users/:id/tweets`（user timeline）：10,000 次/15min（app 级）、900 次/15min（user 级）
- `GET /2/lists/:id/tweets`（List timeline）：900 次/15min
- Recent search：450 次/15min（app）、300 次/15min（user），每请求最多 100 条
- Full-archive search：1 次/秒、300 次/15min，每请求最多 500 条

### 1.3 对金融账号跟踪的直接答案

- **能否只读跟踪金融账号？能。** User timeline 与 List timeline 端点均在 PPU 下可用，$0.005/条。
- **Free 档 2026 年能否读 user timeline？不能。** Free 档 2026-02-06 起对新项目关闭，且此前就只有写权限、无读取。
- **成本测算**：跟踪 20 个 KOL × 每天 10 条新推 × 30 天 = 6,000 条/月 ≈ **$30/月**，低于旧 Basic 的 $200。个人小规模场景下 PPU 其实比旧档位便宜。

---

## 二、官方转售/企业代理（Data Partners）

**结论：个人开发者不可行。**

- 历史上的官方经销商（DataSift、Gnip、NTT DATA）中，Gnip 已于 2014 年被 Twitter 收购并入官方企业产品
- Bloomberg（2015 年起合作金融数据）、Brandwatch、Sprinklr 等持牌集成商均无公开定价，数据费用内嵌在企业平台合同中（年费数万至数百万美元量级）
- Enterprise 直签据报道约 $42,000+/月起
- X 不公开经销商名单与价格；无任何面向个人的低成本转售通道

**合规状态**：合法，但对个人完全不具备可得性。跳过。

---

## 三、灰色路径合规评估（全部不推荐）

| 路径 | 2026-10 现状 | 违反什么 | 结论 |
|---|---|---|---|
| **Nitter** | 2026-08-24 X Corp 发送 C&D（cease & desist）要求永久下架；nitter.net、xcancel.com 等主要公共实例已关闭（zedeus/nitter GitHub；Privacy Guides 论坛, 2026-09） | 未授权自动化抓取、模拟前端访问 | **不推荐**。已死，且自建实例=自担法律风险 |
| **RSSHub Twitter 路由** | 公共实例返回 503；必须配置 `TWITTER_AUTH_TOKEN` 或含 `auth_token`+`ct0` 的登录 Cookie 才能自建使用（RSSHub issue #14910） | 使用登录态 Cookie 做自动化访问，违反 X ToS 的自动化抓取禁令；账号有封禁风险 | **不推荐**。依赖你的账号登录态，账号被封得不偿失 |
| **Apify Twitter Scraper** | 仍活跃运营，原理是拦截 X 内部 GraphQL 接口 | 绕过官方授权接口，违反 ToS；X 曾于 2023–2024 起诉抓取方 | **不推荐**。技术上能跑，法律与服务连续性风险高 |
| **SocialData.tools 等第三方抓取 API** | 持续运营，宣称比官方便宜 20×+（twitterapi.io） | 同上：非授权数据源，无 X 许可 | **不推荐**。对"合规个人工具"是负资产：随时可能被掐断，且把你自己的产品拖入侵权链条 |

**共同问题**：这些路径的数据稳定性完全取决于猫鼠游戏，2026 年 X 的法务+技术双管齐下（Nitter 之死即为证据），作为财富管理工具的信息底座毫无"稳定性"可言。

---

## 四、替代信息路径（重点推荐方向）

### 4.1 金融 KOL 的 Newsletter 与博客 RSS —— 最佳替代

- **Substack**：每个免费 newsletter 都有 RSS，`https://[名字].substack.com/feed`；免费文章全文可读，付费文章仅摘要。主流金融写作者几乎都在此同步
- **ZeroHedge**：`https://feeds.feedburner.com/zerohedge/feed`（官方 feedburner feed）
- **Odd Lots（Bloomberg 播客）**：`https://feeds.megaphone.fm/odd-lots`（免费）
- **Money Stuff（Matt Levine）**：bloomberg.com/opinion 免费网页版 + 免费邮件订阅，完全独立于 X 存在

**优势**：零成本、作者主动发布（授权明确）、RSS 是为机器消费设计的合法接口、无 rate limit 焦虑、内容深度远超推文。

### 4.2 官方机构的 RSS（机构信息 > 推特转述）

- **美联储**：`https://www.federalreserve.gov/feeds/press_all.xml`（全部新闻稿），FOMC 声明、主席讲话均有分类 feed（federalreserve.gov/newsevents/pressreleases/）
- **SEC EDGAR**：每家公司有 atom feed（`/Archives/edgar/data/{CIK}/`），全文搜索结果可订阅为 RSS；官方限流 10 req/sec，对个人绰绰有余
- SEC 新闻稿、讲话也有官方 RSS

**要点**：Fed/SEC/记者的第一手信息源都在 X 之外有官方渠道——**X 上看到的大多数宏观消息，其实是这些 RSS 的滞后转述**。直接订阅源头反而更快。

### 4.3 X Lists 通过官方 API 只读订阅

**可行。** `GET /2/lists/:id/tweets` 在 PPU 下开放，$0.005/条，900 次/15min。架构上：自建一个金融 KOL List → 工具轮询该 List timeline → 一条管道拿到所有成员推文，比逐个拉 user timeline 更省请求次数（请求按次计费的角度看 List 更经济：1 次请求最多带回最多条数）。

---

## 五、成本方案对比表

| 路径 | 月成本 | 可获取内容 | Rate limit | ToS 合规性 | 稳定性 | 适合的架构位置 |
|---|---|---|---|---|---|---|
| Substack/博客 RSS | $0 | KOL 全文（免费部分） | 无实际限制（自建 fetcher，注意礼貌间隔） | ✅ 完全合规（作者授权的分发渠道） | 高 | **默认主信息层** |
| Fed/SEC 官方 RSS | $0 | 宏观+监管一手信息 | SEC 10 req/sec | ✅ 官方提供 | 极高 | **宏观事件层（必装）** |
| X API PPU（List 轮询） | ~$5–30（按 1k–6k 条/月） | List 内全部推文+元数据 | 900 次/15min | ✅ 官方授权 | 高（价格条款可能再变） | 可选付费增强层 |
| X API PPU（search） | 同上，$0.005/条 | 关键词实时搜索 | 450 次/15min | ✅ | 同上 | 事件驱动触发式查询 |
| Nitter | — | — | — | ❌ 已收 C&D | **已死** | 不适用 |
| RSSHub Twitter 路由 | $0 + 自建服务器 | 推文 | 无保障 | ❌ 登录态抓取 | 低（依赖 cookie 存活） | 不适用 |
| Apify/SocialData | $10–50 | 推文 | 无保障 | ❌ 未授权转售 | 低 | 不适用 |
| Enterprise/经销商 | $42,000+ | 全量 firehose | 定制 | ✅ | 极高 | 个人不适用 |

---

## 六、架构建议（本地优先个人工具）

### 6.1 分层设计

```
┌─ L0 官方源（必装，$0）─────────────┐
│ Fed press RSS · SEC EDGAR atom     │  ← 宏观/监管事件，一手信息
├─ L1 KOL 内容层（默认，$0）─────────┤
│ Substack /feed · 博客 RSS · 播客   │  ← 深度分析，全文入库
├─ L2 X 层（可选付费升级）───────────┤
│ X API PPU + 用户自带 key           │  ← 时效性观点/情绪，信号层
│ 模式：轮询自建 List timeline       │
└────────────────────────────────────┘
```

### 6.2 关键设计决策

1. **X 情报层做成可选插件，不做硬依赖**。理由：PPU 价格条款 2024–2026 已变过三轮（$100→$200→PPU），把核心功能绑死在 X 上等于把产品命运交给对方的定价团队。
2. **用户自带 key（BYOK）**。X API PPU 无最低消费，用户在 console.x.com 自充信用点，工具只读 OAuth token + 余额告警。开发者无需代收费用，也规避了 Developer Agreement III.A(e) 禁止"向第三方提供 API token/key"的条款（docs.x.com/developer-terms/agreement，2026-10-03 抓取）。
3. **利用 24h 去重计费**：官方对同一资源 24h 内重复拉取只计费一次。缓存策略对齐这个窗口：本地全量缓存 24h+，增量轮询只取 `since_id` 之后的新推，能把账单压到理论下限。
4. **请求合并**：跟踪多个账号时优先用 List timeline（一次请求覆盖 N 个账号）而非逐个 user timeline。
5. **消费护栏**：设置 PPU 的 billing-cycle spending limit（官方支持）+ 本地日预算熔断，防止监控关键词搜索意外刷爆信用点。

### 6.3 引用与转述的合规边界（依据 Developer Agreement 原文，2026-10-03 抓取）

| 用法 | 合规性 | 依据 |
|---|---|---|
| 本地存储推文、供自己分析/检索 | ✅ 基本安全 | Section II.A(2)："Copy a reasonable amount of and display the X Content on and through your Services to Users"（个人自用属于许可范围） |
| 在**仅自己可见**的工具 UI 中展示推文原文+作者+链接 | ✅ 允许 | 同上，display 权限明确授予 |
| 把推文**全文重新发布**到任何第三方可见渠道（公开博客、群发、另一个网站） | ❌ 违反协议 | Section III.A(d)：禁止 "sell, rent, lease, sublicense, **distribute, redistribute, syndicate**, create derivative works of... the Licensed Material to any third party" |
| 生成**摘要 + 原 tweet 链接**（AI 转述观点、注明出处） | ⚠️ 灰色偏安全 | 属于"分析"许可用途+事实转述；只要不是系统性替代原文分发、且仅限自用展示，风险低 |
| 分享 tweet ID 列表给他人 | ⚠️ 协议已收紧 | 旧版协议允许的 "ID sharing + rehydration" 惯例在现行版本下无独立豁免条款，ID 被归入 "X Content" 一体约束 |

**实操准则**：本地工具内怎么看都行；任何内容一旦要"给别人看"，一律转为"摘要 + x.com 原链接"，绝不批量复制原文。

### 6.4 一句话结论

> 2026 年做合规的个人金融情报工具：**RSS/Newsletter 是免费的正规军，Fed/SEC 官方 feed 是被低估的第一手源；X 官方 API 的 PPU 模式反而让小规模只读跟踪变得比 Basic 时代更便宜（$5–30/月 vs $200/月）——把它设计成用户自带 key 的可选层，其余灰色路径一概不碰。**

---

## 附：来源清单（均为 2026-10-03 检索/抓取）

**官方文档（一手来源）**
- X API 定价（PPU 明细）：https://docs.x.com/x-api/getting-started/pricing
- X API 概览：https://docs.x.com/x-api/getting-started/about-x-api
- Rate limits：https://docs.x.com/x-api/fundamentals/rate-limits
- Developer Agreement（再分发条款）：https://docs.x.com/developer-terms/agreement
- Developer Console：https://console.x.com

**行业与社区佐证**
- PPU 宣布：Gigazine（2026-02-09）
- 档位迁移时间线：devcommunity.x.com（2026-04/06/08 讨论串）、opentweet.io
- Nitter C&D：zedeus/nitter GitHub（issue #1128，2026-08-26）、Privacy Guides 论坛（2026-09）
- RSSHub Twitter 认证要求：DIYgod/RSSHub issue #14910
- 企业数据无公开定价：datarade.ai、fenced.ai、Adweek（2015-09-17）
- Free 档现状佐证：xcrop.io、eden.so、data365.co（2026-04-17）
- 替代源：federalreserve.gov/newsevents/pressreleases/、sec.gov/edgar、Substack 生态例证
