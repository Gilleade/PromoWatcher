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

-- ============================================================
-- Catálogo de produtos (v2)
-- ============================================================

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_title TEXT NOT NULL,
    category TEXT,
    brand TEXT,
    model TEXT,
    variant_label TEXT,
    storage_gb INTEGER,
    ram_gb INTEGER,
    release_year INTEGER,
    variant_key TEXT NOT NULL,
    image_url TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    merged_into_product_id INTEGER REFERENCES products (id),
    lowest_price_ever REAL,
    lowest_price_ever_at TEXT,
    last_price REAL,
    last_price_at TEXT,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_products_variant_key ON products (variant_key);
CREATE INDEX IF NOT EXISTS idx_products_brand_model ON products (brand, model);
CREATE INDEX IF NOT EXISTS idx_products_status ON products (status);

CREATE TABLE IF NOT EXISTS product_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products (id),
    spec_key TEXT NOT NULL,
    spec_value TEXT NOT NULL,
    confidence REAL,
    source TEXT NOT NULL DEFAULT 'DETERMINISTIC',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (product_id, spec_key)
);

CREATE TABLE IF NOT EXISTS product_price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products (id),
    promotion_id INTEGER REFERENCES promotions (id),
    price REAL NOT NULL,
    old_price REAL,
    coupon TEXT,
    store_domain TEXT,
    source_chat_title TEXT,
    is_bug_candidate INTEGER NOT NULL DEFAULT 0,
    deviation_percent REAL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_price_history_product
    ON product_price_history (product_id, recorded_at);

CREATE TABLE IF NOT EXISTS product_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products (id),
    image_url TEXT,
    local_path TEXT,
    source TEXT NOT NULL DEFAULT 'TELEGRAM_MEDIA',
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE REFERENCES products (id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS product_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE REFERENCES products (id),
    enabled INTEGER NOT NULL DEFAULT 1,
    max_price REAL,
    send_to_telegram INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS coupons_standalone (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_message_id INTEGER NOT NULL REFERENCES raw_messages (id),
    code TEXT,
    discount_label TEXT,
    description TEXT,
    store_name TEXT,
    store_domain TEXT,
    url TEXT,
    dedupe_key TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    source_chat_title TEXT,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    repeat_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_coupons_dedupe_key ON coupons_standalone (dedupe_key);

CREATE TABLE IF NOT EXISTS product_match_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promotion_id INTEGER NOT NULL UNIQUE REFERENCES promotions (id),
    extracted_specs_json TEXT NOT NULL,
    candidate_products_json TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_match_queue_status ON product_match_queue (status);

CREATE TABLE IF NOT EXISTS product_merges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_product_id INTEGER NOT NULL,
    target_product_id INTEGER NOT NULL REFERENCES products (id),
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
