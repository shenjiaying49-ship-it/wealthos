-- WealthOS schema v1 (架构文档 D3)
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

-- ── 财务事实域 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  institution TEXT NOT NULL,
  country TEXT, currency TEXT NOT NULL,
  account_type TEXT NOT NULL,        -- bank/brokerage/cash/property/crypto/pension/loan
  is_asset INTEGER NOT NULL DEFAULT 1,
  is_demo INTEGER NOT NULL DEFAULT 0, -- 示例数据（可一键清除）
  opened_at TEXT, closed_at TEXT, notes TEXT
);

CREATE TABLE IF NOT EXISTS instruments (
  symbol TEXT PRIMARY KEY,
  name TEXT, isin TEXT,
  asset_class TEXT,                  -- equity/etf/bond/crypto/fx/cash/realestate
  asset_subclass TEXT, exchange TEXT,
  currency TEXT, country TEXT, sector TEXT, region TEXT,
  stooq_symbol TEXT, yahoo_symbol TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS activities (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  symbol TEXT NOT NULL,
  activity_type TEXT NOT NULL,       -- BUY/SELL/DIVIDEND/FEE/INTEREST/TRANSFER_IN/TRANSFER_OUT/SPLIT/CONVERSION
  quantity REAL NOT NULL, price REAL, currency TEXT NOT NULL,
  fx_rate_to_base REAL, fees REAL DEFAULT 0, tax REAL DEFAULT 0,
  trade_date TEXT NOT NULL, settled_at TEXT,
  source TEXT DEFAULT 'manual', raw_ref TEXT,
  UNIQUE(account_id, symbol, activity_type, quantity, price, trade_date)
);

CREATE TABLE IF NOT EXISTS holdings (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  as_of TEXT NOT NULL,
  symbol TEXT NOT NULL,              -- 'CASH:USD' 表示现金
  quantity REAL NOT NULL,
  currency TEXT NOT NULL,
  price REAL,                        -- 该币种计价
  source TEXT DEFAULT 'manual',
  UNIQUE(account_id, as_of, symbol)
);

CREATE TABLE IF NOT EXISTS valuations (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  as_of TEXT NOT NULL,
  market_value REAL NOT NULL,        -- 账户币种
  currency TEXT NOT NULL,
  fx_rate_to_base REAL,
  method TEXT DEFAULT 'auto',
  UNIQUE(account_id, as_of)
);

CREATE TABLE IF NOT EXISTS fx_rates (
  as_of TEXT NOT NULL, base_ccy TEXT NOT NULL, quote_ccy TEXT NOT NULL,
  rate REAL NOT NULL, source TEXT,
  PRIMARY KEY (as_of, base_ccy, quote_ccy)
);

-- ── 市场数据域 ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS price_daily (
  symbol TEXT NOT NULL, as_of TEXT NOT NULL,
  open REAL, high REAL, low REAL, close REAL, close_adj REAL,
  volume REAL, currency TEXT, source TEXT,
  PRIMARY KEY (symbol, as_of)
);
CREATE TABLE IF NOT EXISTS price_latest (
  symbol TEXT PRIMARY KEY, price REAL, currency TEXT, as_of TEXT, source TEXT, fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS macro_series (
  series_id TEXT NOT NULL, as_of TEXT NOT NULL, value REAL, source TEXT,
  PRIMARY KEY (series_id, as_of)
);

-- ── 信息域（Source Graph 骨架）─────────────────────────────
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY, name TEXT, kind TEXT, tier TEXT, reliability TEXT,
  url TEXT, interval_min INTEGER, enabled INTEGER DEFAULT 1,
  last_fetch TEXT, last_status TEXT
);
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY,
  source_id TEXT NOT NULL,
  ext_id TEXT,
  title TEXT NOT NULL, summary TEXT, url TEXT,
  published_at TEXT, fetched_at TEXT,
  content_hash TEXT, dedup_key TEXT UNIQUE,
  label TEXT,                        -- fact/expectation/analysis/opinion/signal
  entities_json TEXT,                -- 命中的图实体
  relevance REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  event_type TEXT, primary_entity TEXT, period TEXT,
  occurred_at TEXT, payload_json TEXT, evidence_json TEXT,
  reliability TEXT, UNIQUE(event_type, primary_entity, occurred_at)
);
CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY, type TEXT, name TEXT, aliases_json TEXT
);
CREATE TABLE IF NOT EXISTS entity_edges (
  from_entity TEXT NOT NULL, edge_type TEXT NOT NULL,
  to_entity TEXT NOT NULL, weight REAL NOT NULL,
  evidence_item_id INTEGER, created_at TEXT,
  PRIMARY KEY (from_entity, edge_type, to_entity)
);

-- ── 分析域 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exposures (
  as_of TEXT NOT NULL, dimension TEXT NOT NULL, key TEXT NOT NULL,
  value_base REAL, pct REAL,
  PRIMARY KEY (as_of, dimension, key)
);
CREATE TABLE IF NOT EXISTS opportunities (
  id INTEGER PRIMARY KEY,
  title TEXT, category TEXT, status TEXT DEFAULT 'open',
  payload_json TEXT, created_at TEXT, decided_at TEXT, outcome TEXT
);
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL, as_of TEXT NOT NULL,
  data_snapshot_hash TEXT, content TEXT, content_json TEXT,
  model_meta_json TEXT, created_at TEXT
);

-- ── 教育域 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_nodes (
  concept TEXT PRIMARY KEY, domain TEXT, prereq_json TEXT,
  importance INTEGER DEFAULT 3,
  status TEXT DEFAULT 'unknown',     -- unknown/learning/known/weak
  mastery_score REAL DEFAULT 0, last_reviewed TEXT
);
CREATE TABLE IF NOT EXISTS lessons (
  id INTEGER PRIMARY KEY,
  concept TEXT NOT NULL, date TEXT,
  content_json TEXT, result TEXT,
  UNIQUE(concept, date)
);

-- ── 运维域 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fetch_log (
  id INTEGER PRIMARY KEY, job TEXT, target TEXT,
  status TEXT, detail TEXT, items INTEGER, ts TEXT
);
CREATE TABLE IF NOT EXISTS llm_calls (
  id INTEGER PRIMARY KEY,
  prompt_hash TEXT, provider TEXT, model TEXT,
  prompt TEXT, response TEXT,
  input_tokens INTEGER, output_tokens INTEGER,
  cache_hit INTEGER DEFAULT 0, created_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY, report_id INTEGER,
  check_name TEXT, passed INTEGER, detail TEXT, ts TEXT
);

CREATE INDEX IF NOT EXISTS idx_items_rel ON items(relevance DESC);
CREATE INDEX IF NOT EXISTS idx_items_pub ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_holdings_asof ON holdings(as_of);
