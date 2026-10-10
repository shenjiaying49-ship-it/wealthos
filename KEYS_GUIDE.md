# 接口打通保姆级指南（KEYS GUIDE）

> 网页版（带实时状态检测与一键复制）在应用内「⚙️ 接口」页。本文件是同一内容的离线版。

## 通用：所有 Key 写进同一个文件

所有配置都是 `KEY=值` 每行一条，写进 `~/.wealthos/env`：

```bash
mkdir -p ~/.wealthos && cat >> ~/.wealthos/env << 'EOF'
WEALTHOS_XXX_KEY=你的值
EOF
```

- 改完刷新网页「⚙️ 接口」页即可看到状态变化（无需重启即可检测；LLM 等运行时行为需重启服务）。
- 编辑已有内容：`open -e ~/.wealthos/env`
- 自检命令：`uv run wealthos doctor`（配置了 Telegram 会真发一条测试消息）
- Key 只存在本机，系统不上传任何服务器。

## 1. LLM 大脑（AI 模式）— 不配也可用（确定性模式）

| 方案 | 费用 | 适合 |
|---|---|---|
| A. Ollama 本地 | 免费 | 零门槛、隐私最优、国内直连；稍慢 |
| B. 智谱 GLM | 有免费模型；付费约 ¥5–30/月 | 国内直连、人民币付款、OpenAI 兼容 |
| C. OpenAI / Anthropic | 按量 ~$5/月起 | 效果上限高；需海外支付与网络环境 |

**A. Ollama（推荐起步）**
1. https://ollama.com 下载 macOS 版安装；
2. 终端运行 `ollama pull qwen2.5:7b`（内存 8G 以下用 `qwen2.5:3b`）；
3. env 写入：
   ```
   WEALTHOS_LLM_PROVIDER=ollama
   WEALTHOS_LLM_MODEL=qwen2.5:7b
   ```
4. 重启后生成简报，末尾显示「AI 增强已开启」即成功。

**B. 智谱 GLM**
1. https://open.bigmodel.cn 注册；
2. 「API Keys」→ 新建并复制（只显示一次）；
3. env 写入（BASE_URL 必须原样照抄）：
   ```
   WEALTHOS_LLM_PROVIDER=openai
   WEALTHOS_LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
   WEALTHOS_LLM_API_KEY=你的Key
   WEALTHOS_LLM_MODEL=glm-4-flash
   ```

**C. OpenAI**：platform.openai.com → API keys → Create（sk-… 只显示一次）→ Billing 充 $5+；
   ```
   WEALTHOS_LLM_PROVIDER=openai
   WEALTHOS_LLM_API_KEY=sk-…
   WEALTHOS_LLM_MODEL=gpt-4o-mini
   ```
   **Anthropic** 同理（console.anthropic.com）：`PROVIDER=anthropic`、`MODEL=claude-sonnet-4-5`。

## 2. Telegram 推送（免费，~10 分钟）

> ⚠️ 中国大陆需自备可用网络环境；不方便就跳过，网页版功能完整。

1. 装 Telegram，搜索 **@BotFather**（认准蓝色认证勾）→ START → 发送 `/newbot`；
2. 依次回答：显示名（随意）/ 用户名（必须 `bot` 结尾，如 `my_wealthos_01_bot`）；
3. BotFather 回复中的 `7123456789:AAH9x…` 即 **Token**（保密；泄露用 `/revoke` 换新）；
4. 搜索你的 bot 用户名 → START → 随便发一句「hi」（**必须先发**，否则 bot 无权给你发消息）；
5. 浏览器打开 `https://api.telegram.org/bot<你的Token>/getUpdates`，在 JSON 里找 `"chat":{"id":数字` → 那就是 **Chat ID**（个人号为正数）；
6. env 写入：
   ```
   WEALTHOS_TELEGRAM_TOKEN=粘贴Token
   WEALTHOS_TELEGRAM_CHAT_ID=你的ChatID
   ```
7. 运行 `uv run wealthos doctor` → 收到测试消息即打通。

## 3. FRED 利率数据（免费，~3 分钟）

1. https://fred.stlouisfed.org → Register（邮箱即可）；
2. 登录 → 右上角用户菜单 → **API Keys**（已自动生成）→ Copy；
3. env 写入 `WEALTHOS_FRED_KEY=粘贴`。
（不配也有无 key 备源，属锦上添花。）

## 4. 券商 API（开户后再做 · Roadmap 第 4 步）

- **长桥**：开户后 https://open.longbridge.com → 开发者中心认证 → App Key/Secret/Access Token；系统端接入已预留。
- **IBKR**：Client Portal → Performance & Reports → **Flex Queries**：新建含 Positions/Balances 的查询拿 Query ID，再生成 Flex Token——天生只读、免网关，最适合自用。

## 5. X 情报信号（可选付费，开发中）

- https://developer.x.com 注册 → 绑卡（送 $20 额度，按量付费）→ Bearer Token；
- env 写入 `WEALTHOS_X_BEARER_TOKEN=…`；系统按合规设计（List 轮询 + 24h 去重 + 消费熔断），实装后即可启用。

## 6. 雪球行情（可选 · 中文市场兜底）

未配置则行情走 Yahoo/Stooq。合规路径：只用你自己的 `xq_a_token`（Agent-Reach 同款最小 Cookie 方案）。

1. 电脑 Chrome 登录 https://xueqiu.com ；
2. F12 → Network → 刷新 → 点任一 xueqiu.com 请求 → Headers 里复制 `Cookie:` 中 `xq_a_token=…` 这一段；
3. env 写入 `WEALTHOS_XUEQIU_COOKIE=xq_a_token=粘贴`。

## 7. Exa 语义搜索（可选 · 深度研究）

1. https://dashboard.exa.ai 注册 → API Keys 复制；
2. env 写入 `WEALTHOS_EXA_API_KEY=粘贴`。

## 附：信息源架构与 Agent-Reach 的对应关系

本项目参考 Panniantong/Agent-Reach（92k★, MIT）的方法论接入多平台：
| Agent-Reach 通道 | WealthOS 落地 |
|---|---|
| 华尔街见闻公开 API（finance 平台公开通道法） | ingest/wscn.py（默认开启，中文全球快讯） |
| Jina Reader（web.md） | providers/reader.py（证据层抓原文，直连兜底） |
| 雪球最小 Cookie（finance.md） | providers/xueqiu.py（BYO，默认关） |
| Exa 搜索（search.md） | providers/exa.py（BYO，默认关） |
| Twitter 合规边界 | X API PPU 层（设计预留，见调研报告 D） |
