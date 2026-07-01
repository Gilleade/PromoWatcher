CREATE TABLE IF NOT EXISTS raw_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    chat_title TEXT,
    sender_id INTEGER,
    message_text TEXT,
    message_date TEXT,
    has_media INTEGER NOT NULL DEFAULT 0,
    media_type TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_raw_messages_chat_msg
    ON raw_messages (chat_id, telegram_message_id);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    alert_type TEXT NOT NULL DEFAULT 'PRODUCT_RULE',
    required_terms TEXT,
    optional_terms TEXT,
    excluded_terms TEXT,
    min_price REAL,
    max_price REAL,
    min_discount_percent REAL,
    bug_mode INTEGER NOT NULL DEFAULT 0,
    min_score INTEGER NOT NULL DEFAULT 0,
    send_to_telegram INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS promotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_message_id INTEGER NOT NULL REFERENCES raw_messages (id),
    title_guess TEXT,
    price REAL,
    old_price REAL,
    discount_percent REAL,
    coupon TEXT,
    source_chat_title TEXT,
    original_links TEXT,
    selected_original_url TEXT,
    resolved_url TEXT,
    clean_url TEXT,
    link_status TEXT,
    store_domain TEXT,
    dedupe_key TEXT,
    status TEXT,
    score INTEGER,
    matched_alert_id INTEGER REFERENCES alerts (id),
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    repeat_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_promotions_dedupe_key ON promotions (dedupe_key);
CREATE INDEX IF NOT EXISTS idx_promotions_clean_url ON promotions (clean_url);
CREATE INDEX IF NOT EXISTS idx_promotions_resolved_url ON promotions (resolved_url);

CREATE TABLE IF NOT EXISTS promotion_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promotion_id INTEGER NOT NULL REFERENCES promotions (id),
    raw_message_id INTEGER NOT NULL REFERENCES raw_messages (id),
    chat_title TEXT,
    message_date TEXT,
    original_url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_occurrences_promotion_id
    ON promotion_occurrences (promotion_id);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promotion_id INTEGER NOT NULL REFERENCES promotions (id),
    alert_id INTEGER REFERENCES alerts (id),
    channel TEXT NOT NULL,
    message_sent TEXT,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'SENT',
    error_message TEXT
);
