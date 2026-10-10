# WealthOS — AI Personal Wealth Intelligence OS

本地优先的个人财富情报系统：真实财务数据 × 全球金融信息 × AI 研究/解释/教育。
设计文档见 `docs/`（A~M 十三份架构文档）。

## 快速开始

```bash
cd wealthos
uv sync            # 或: pip install -e .[dev]
uv run wealthos init-db
uv run wealthos import samples/accounts.csv
uv run wealthos import samples/holdings_2026-10-02.csv
uv run wealthos import samples/activities.csv
uv run wealthos fetch          # 行情 + 汇率 + 新闻（网络）
uv run wealthos brief --print  # 生成并打印今日晨报（无 LLM key 也能跑）
uv run wealthos serve          # 打开 http://127.0.0.1:8787
```

## LLM（可选，BYOK）

无 key 时系统以**确定性模式**运行（简报由模板+计算生成，全部数字可溯源）。
**保姆级配置步骤见网页「⚙️ 接口」页或 [KEYS_GUIDE.md](KEYS_GUIDE.md)**；
所有 key 写进 `~/.wealthos/env`（每行一条 `KEY=值`），自检命令：

```bash
uv run wealthos doctor   # 检查 LLM/Telegram/FRED/X 状态；配好 Telegram 会真发测试消息
```

三个 LLM 方案（详见指南）：Ollama 本地（免费）/ 智谱 GLM（国内直连）/ OpenAI·Anthropic。

## 命令

| 命令 | 作用 |
|---|---|
| `init-db` | 建库 + 种子数据（Source Graph / 课程 / 信息源） |
| `import <path>` | 导入 CSV（accounts/holdings/activities）或 IBKR Flex XML |
| `fetch` | 拉取行情、汇率、新闻（三级去重） |
| `brief [--print]` | 生成 Daily Brief（绑定数据快照哈希） |
| `lesson [--print]` | 今日一课（知识图谱驱动） |
| `status` | 数据新鲜度总览 |
| `serve` | 启动 API + Web UI + 定时任务 |

## 目录

```
wealthos/
├── wealthos/          # Python 包
│   ├── engine/        # 净值/敞口计算（确定性）
│   ├── importers/     # CSV / IBKR Flex
│   ├── providers/     # 行情(Stooq/Yahoo可选) 汇率(frankfurter)
│   ├── ingest/        # RSS 摄取 / 去重 / Source Graph 相关性
│   └── agents/        # LLM 抽象 / Brief / 教育 / 审计器
├── config/            # sources.yaml entities.yaml lessons.yaml
├── samples/           # 样例数据（含合成 Flex XML）
├── web/               # 静态前端（零构建）
└── tests/             # pytest（离线，网络用 MockTransport）
```
