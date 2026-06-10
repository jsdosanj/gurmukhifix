-- Schema for gurmukhifix corrections database
-- SPDX-License-Identifier: MIT

CREATE TABLE IF NOT EXISTS corrections (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    script             TEXT NOT NULL,
    original_sequence  TEXT NOT NULL,
    corrected_sequence TEXT NOT NULL,
    context_before     TEXT,
    context_after      TEXT,
    source_document    TEXT,
    reviewer_id        TEXT,
    timestamp          DATETIME DEFAULT CURRENT_TIMESTAMP,
    confidence_delta   REAL,
    rule_applied       TEXT
);

CREATE TABLE IF NOT EXISTS correction_stats (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    script             TEXT NOT NULL,
    original_sequence  TEXT NOT NULL,
    corrected_sequence TEXT NOT NULL,
    count              INTEGER DEFAULT 1,
    promoted           INTEGER DEFAULT 0,
    UNIQUE(script, original_sequence, corrected_sequence)
);

CREATE INDEX IF NOT EXISTS idx_corrections_script ON corrections(script);
CREATE INDEX IF NOT EXISTS idx_corrections_original ON corrections(original_sequence);
CREATE INDEX IF NOT EXISTS idx_stats_script_orig ON correction_stats(script, original_sequence);
