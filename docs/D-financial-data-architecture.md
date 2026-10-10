# D. Financial Data Architecture — 金融数据架构

**日期**：2026-10-03 · 依据：research-notes/A（数据源）、B（数据模型调研）、F（银行券商 API）

## D1. 设计原则

1. **Local-first**：SQLite 单文件（可选 SQLCipher 加密），一切可离线。
2. **三层分离**（借鉴 OpenBB + Ghostfolio）：`原始摄取层（raw）→ 标准模型层（canonical）→ 派生分析层（derived）`。换数据源只动第一层。
3. **快照 + 事件双轨**（借鉴 Maybe/Flex Query 节奏）：账户以"每日 EOD 快照"为准绳，交易以"事件流水"为明细；两者可互相校验。
4. **多币种一等公民**：任何金额字段都必须有币种；任何快照都必须记录当日汇率。
5. **全部可溯源**：每行派生数据带 `source + fetched_at + as_of`。

## D2. 存储

```
wealth.db (SQLite, WAL mode, 可选 SQLCipher)
├── 财务事实域: accounts / holdings / activities / valuations / fx_rates
├── 市场数据域: instruments / price_daily / price_intraday / macro_series
├── 信息域:   sources / items / events / entity_edges (Source Graph)
├── 分析域:   exposures / signals / opportunities / reports
├── 教育域:   knowledge_nodes / lessons / quiz_results
└── 运维域:   fetch_log / llm_calls / sync_state
```

单机单用户规模（10 年 × 20 账户 × 日频 ≈ 百万行级）SQLite 绰绰有余；向量检索用 sqlite-vec（新闻 embedding），不引 Postgres。

## D3. 核心实体（融合 Ghostfolio Activity + Maybe Entry + PP Classification）

### 财务事实域

```sql
-- 账户：Maybe 的 asset/liability + 机构/地区/税务居中维度
accounts(id, name, institution, country, currency, account_type,      -- bank/brokerage/cash/property/crypto/pension/loan
         is_asset, opened_at, closed_at, notes)

-- 证券主数据（Ghostfolio SymbolProfile 思路）
instruments(symbol PK, name, isin, asset_class,     -- equity/bond/etf/crypto/fx/realestate/cash
            asset_subclass, exchange, currency, country, sector, region,
            proxy_ticker)   -- 各行情源的 symbol 映射 (yahoo/stooq/…)

-- 交易/事件流水（Ghostfolio Activity 枚举 + PP 全谱系）
activities(id, account_id, symbol, activity_type,   -- BUY/SELL/DIVIDEND/FEE/INTEREST/
                                             -- TRANSFER_IN/TRANSFER_OUT/SPLIT/CONVERSION
         quantity, price, currency, fx_rate_to_base, fees, tax,
         trade_date, settled_at, source, raw_ref)

-- 估值快照（Maybe 的 Valuation 建模）
valuations(id, account_id, as_of_date, market_value, currency,
           fx_rate_to_base, method)   -- auto/manual/imported

-- 汇率（frankfurter/ECB 日频 + 历史）
fx_rates(as_of_date, base_ccy, quote_ccy, rate, source)
```

### 市场数据域

```sql
price_daily(symbol, as_of_date, open, high, low, close_adj, volume, currency, source)
price_intraday(symbol, ts, price, source)          -- 仅持仓/自选，TTL 清理
macro_series(series_id, as_of_date, value, source) -- FRED DGS10 / ECB / DBnomics(BoJ)…
```

### 信息域（Source Graph 骨架，详见 H 报告）

```sql
sources(id, name, kind,            -- rss/official/x/newsletter/earnings/research
        tier, reliability, config_json, enabled)
items(id, source_id, ext_id, title, summary, url, published_at,
      fetched_at, content_hash, dedup_key, embedding)
events(id, event_type,             -- rate_decision/earnings/cpi/filing/macro_release
       primary_entity, period, occurred_at, payload_json)
entity_edges(from_entity, edge_type, to_entity, weight, evidence_item_id, created_at)
  -- entity: 央行/货币/资产/公司/行业/宏观概念/我的账户
```

### 分析与教育域

```sql
exposures(as_of_date, dimension,      -- currency/country/sector/asset_class/institution/single_symbol
          key, weight_base_ccy, pct)
signals(id, item_id, event_id, signal_type, direction, confidence, created_at)
opportunities(id, title, category,           -- banking/brokerage/cash_mgmt/diversification/tax
              status, payload_json, created_at, decided_at, outcome)
reports(id, kind, as_of_date, data_snapshot_hash, content, model_meta_json, created_at)
knowledge_nodes(id, concept, status,     -- known/learning/weak/unknown
                mastery_score, last_seen)
lessons(id, concept_node_id, date, content, quiz_question, result)
```

## D4. Provider 抽象（Ghostfolio/OpenBB 模式的轻量版）

```python
class MarketDataProvider(Protocol):
    name: str
    def supports(self, ins: Instrument) -> bool: ...
    def daily(self, symbol, start, end) -> list[PriceBar]: ...
    def quote(self, symbols) -> dict[str, Quote]: ...

# 注册顺序即优先级；每个 provider 自带限速/缓存/降级
REGISTRY = [
    YahooProvider(cache=LocalCache(ttl="12h"), rate=Polite(0.5/s)),   # 灰区主力
    StooqProvider(...),          # 日线兜底（实测覆盖 HK/JP 全市场）
    TwelveDataProvider(...),     # 实时快照（免费 800/天）
    EODHDProvider(...),          # 可选付费升级（$19.99/月）
]
class Resolver:  # Wealthfolio 的 resolver 思路
    def resolve(self, ins) -> Provider: ...
```

- 摄取任务全部走**每日定时批处理**（收盘后一次），盘中快照按需拉取且严格缓存——对齐 yfinance 的 IP 限流现实（research-notes/A：一次 78 请求即可能被拦）。
- 失败处理：指数退避 → 切换 provider → 标记 stale 并在 UI 显示"数据截至 X 日"，绝不静默用旧数冒充新数。

## D5. 账户同步架构（结论来自 research-notes/F）

```
MVP:   手动层 —— CSV/Flex 报告拖入 / 定向投递文件夹 (~/WealthOS/inbox/)
              + 通用 CSV 映射器（记住映射模板）+ IBKR Flex XML 解析器
V2:    自动层 —— IBKR Flex Query (token+query id, 免费免网关免会话)
              → LongPort OpenAPI (云端直连, OAuth)
              → Tiger OpenAPI (RSA 签名直连)
              → [可选] Futu OpenD / SnapTrade(美股) / CCXT(加密)
不做:   港/日/新银行自动同步（结构性不可行），永久走文件导入
```

所有连接器统一实现 `InstitutionConnector` 接口：`fetch_positions() / fetch_balances() / fetch_activities(since)`，输出直接落到 activities/valuations，并保留 raw payload 到 `raw/` 目录（可重放）。

## D6. 数据质量规则（写进导入器）

1. 双轨校验：`Σ(昨日持仓×价格±今日交易) ≈ 今日快照`，偏差 >1% 告警。
2. 多币种审计：每笔 activity 落库时同时记 `fx_rate_to_base`；净值曲线只能用历史汇率重算，禁止用现价汇率回溯（防收益率失真）。
3. Corporate actions：SPLIT/CONVERSION 必须生成，否则 TWR 全错——导入器检测"价格跳变 >50% 且无交易"时提示补录 split。
4. Point-in-time：macro_series/price_daily 的 `as_of` 与 `fetched_at` 分开存，agent 永远能看到"当时知道什么"（借鉴 TradingAgents 的 PIT 完整性）。
