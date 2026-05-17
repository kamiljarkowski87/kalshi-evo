-- Schema bazy danych kalshi-evo

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    title TEXT,
    category TEXT,
    side TEXT NOT NULL,                    -- yes | no
    my_prob_at_entry REAL,
    market_prob_at_entry REAL,
    edge REAL,
    price_cents INTEGER,
    contracts INTEGER,
    bet_usd REAL,
    bet_pct REAL,
    debate_quality TEXT,
    confidence TEXT,
    data_sources_used TEXT,
    strategy TEXT DEFAULT 'balanced',
    outcome TEXT,                          -- WIN | LOSS | PENDING
    pnl_usd REAL,
    order_id TEXT,
    status TEXT DEFAULT 'open',            -- open | closed | cancelled
    created_at TEXT DEFAULT (datetime('now')),
    closed_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS debate_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER REFERENCES trades(id),
    ticker TEXT NOT NULL,
    round1_json TEXT,
    round2_json TEXT,
    synthesis_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE NOT NULL,
    bets_placed INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    gross_pnl REAL DEFAULT 0,
    bankroll_end REAL,
    markets_scanned INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_category ON trades(category);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at);
