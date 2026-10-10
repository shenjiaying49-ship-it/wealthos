# L. Security Architecture — 安全架构

**日期**：2026-10-03 · 对应用户第三十一节 · 参考实践：rotki（SQLCipher）、Actual（E2E+CRDT）、Firefly III（importer 凭证隔离）、Wealthfolio（BYOK）

## L1. 威胁模型（个人自用工具的现实威胁排序）

| # | 威胁 | 现实性 | 本架构的对策 |
|---|---|---|---|
| 1 | 本机失窃/共用电脑 | 中 | 可选 SQLCipher 全库加密 + OS 用户账户隔离 |
| 2 | **API key 泄漏**（LLM/X API/FRED 等在配置文件里） | 高 | 全部进系统 keychain，绝不落盘明文 |
| 3 | 凭证误提交到 git/备份同步到网盘 | 高 | 数据目录白名单管理 + .gitignore 强制 + 备份加密 |
| 4 | LLM 供应商侧隐私（我的财务数据发给 API） | 中 | Privacy Filter 脱敏层（用户第三节要求） |
| 5 | 恶意依赖（pip 供应链） | 低-中 | lockfile + 依赖审计 + 最小依赖原则 |
| 6 | 券商 token 被工具误用下单 | 低（但后果重） | 只读设计（见 L4） |
| 7 | 网页投毒/提示注入（新闻文本里藏指令） | 中 | 摄取内容与 prompt 的隔离（见 L5） |

## L2. 本地优先与加密

```
~/.wealthos/
├── wealth.db          # SQLite；可选 --encrypt 启用 SQLCipher（密码存 keychain）
├── raw/               # 原始 payload（90天滚动）——与库同盘加密策略
├── backups/           # 每日自动备份（保留 30 份），导出时 AES 加密
└── config.yaml        # 仅非敏感配置；一切 secret 引用 keychain 条目名
```

- 备份：`sqlite3 .backup` + 每日定时；**导出/同步到网盘前必须用户显式确认并默认加密**（威胁 #3 的关键防线）。
- 未来多端（V3）：走 Actual 路线（CRDT + E2E 加密），不自造。

## L3. 凭证管理（绝不保存的东西）

**绝不存储**：银行密码、券商交易密码、任何登录密码。
**存储的只有**（全部 keychain，macOS Keychain / Windows Credential Manager）：

| 凭证 | 用途 | 权限特征 |
|---|---|---|
| LLM API key | agent 调用 | 用户自有账号（BYOK） |
| FRED / CoinGecko / Twelve Data key | 只读数据 | 免费档 |
| X API token（可选） | List 轮询 | 只读 scope |
| IBKR Flex token + query id | 拉报表 | **天生只读**（V2） |
| LongPort/Tiger 凭证 | 查询接口 | 只调用查询类（V2） |

X API 特别注意：BYOK 设计同时规避 Developer Agreement III.A(e)（禁止向第三方提供 token）——token 只在本机使用，永不经过任何服务器（research-notes/D §6.2）。

## L4. 只读边界（券商连接的三重防线）

1. 代码层：只实现查询接口（positions/balances/activities），**下单接口代码根本不写**；
2. 权限层：富途交易解锁密码不开通；IBKR 只用 Flex（报表接口无交易能力）；
3. 审计层：connector 层网络调用白名单（域名+方法），任何非 GET/查询端点的调用直接拒绝并告警。

## L5. LLM 隐私：Privacy Filter 分层脱敏

```
Raw Financial Data                发送给 LLM 的
(账户/持仓/交易)                   ↓ 分层
                    Layer 0 聚合层: 只有敞口百分比、币种、资产类别      ← Daily Brief 默认用这层
                    Layer 1 匿名层: + 匿名化的持仓结构（"美股ETF-A"）    ← 组合分析用
                    Layer 2 明细层: 真实 symbol/金额（本地 Ollama 或用户显式开启） ← 财报/深研用
```

- 配置项 `privacy_level: strict(default)/balanced/full`；strict 下 brief/Chat 只发 Layer 0-1。
- 新闻/财报等**公开内容**不走 filter（它们不含隐私）。
- 日志中 LLM 请求体默认脱敏存储（金额替换为桶：`$10k-50k`），完整请求仅在 `audit_mode` 下保留于本地。

## L6. 提示注入防护（情报层的特有风险）

新闻/推文/transcript 是不可信输入，可能包含"忽略以上指令"类文本：
1. 摄取内容**永不直接拼进 system prompt**——只能作为 tool 返回值/数据字段传入，且外层包 ` <untrusted_content>` 标记；
2. agent 输出若包含"执行/访问/发送"类动作意图 → 审计器拦截（本产品本来就无外发能力，纵深防御）；
3. URL 引用只允许来自白名单域的 fetched 结果，LLM 编造的链接上不了证据层。

## L7. 供应链与运行时

- `uv`/pip lockfile 固定版本；CI 跑 `pip-audit`；依赖数控制在最小（MVP < 40 个直接依赖）。
- web 界面默认绑定 127.0.0.1（不暴露局域网）；若用户开启远程访问，强制设置访问口令 + 提示风险。
- 无遥测、无云端组件——"数据不出本机"是可以被验证的承诺（代码审计即可确认）。

## L8. 合规与免责（产品层）

- UI 常驻免责声明（Chat 与机会卡片处）：AI 输出为信息与研究辅助，不构成投资建议；最终决策由用户做出（用户第三十节"禁止假确定性"的产品化表达）。
- 数据来源合规矩阵已内置（research-notes 各报告）：Yahoo 灰区仅个人低频、RSS 只存摘要+链接、X 内容不再分发、机构研究摘要+出处标注。
