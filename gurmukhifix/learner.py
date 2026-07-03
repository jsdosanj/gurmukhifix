"""Learning and Adaptation Layer for gurmukhifix.

Stores confirmed manual corrections in SQLite and promotes patterns to the
primary confusion dictionary once they have been confirmed at least
``_PROMOTION_THRESHOLD`` times (a frequency threshold, not a Bayesian model).
Promoted pairs can be fed back into :class:`~gurmukhifix.corrector.CharacterCorrector`
so the tool improves on a corpus over time.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_DB = Path(__file__).parent.parent / "corrections.db"
_SCHEMA_SQL = Path(__file__).parent.parent / "schema.sql"
_PROMOTION_THRESHOLD = 10  # instances before promoting to primary dictionary

logger = logging.getLogger(__name__)


class CorrectionStore:
    """Manages the corrections SQLite database."""

    def __init__(self, db_path: Path | str = _DEFAULT_DB) -> None:
        # Preserve special SQLite strings (e.g. ":memory:") and URI filenames,
        # and only coerce real filesystem paths to Path.
        if isinstance(db_path, Path):
            self.db_path: Path | str = db_path
        elif isinstance(db_path, str):
            if db_path == ":memory:" or db_path.startswith("file:"):
                self.db_path = db_path
            else:
                self.db_path = Path(db_path)
        else:
            self.db_path = Path(db_path)

        if isinstance(self.db_path, Path):
            self._conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        else:
            # For URI-style filenames, enable SQLite URI handling
            self._conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                uri=isinstance(self.db_path, str) and self.db_path.startswith("file:"),
            )
        self._conn.row_factory = sqlite3.Row
        # Concurrency hardening: WAL lets readers and a writer coexist, and a
        # busy timeout makes concurrent writers wait rather than fail outright.
        self._conn.execute("PRAGMA busy_timeout = 30000")
        try:
            self._conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error:  # pragma: no cover - e.g. some in-memory/URI cases
            pass
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist (idempotent)."""
        if _SCHEMA_SQL.exists():
            sql = _SCHEMA_SQL.read_text(encoding="utf-8")
        else:
            sql = _FALLBACK_SCHEMA
        self._conn.executescript(sql)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def record_correction(
        self,
        *,
        script: str,
        original_sequence: str,
        corrected_sequence: str,
        context_before: str = "",
        context_after: str = "",
        source_document: str = "",
        reviewer_id: str = "",
        confidence_delta: float = 0.0,
        rule_applied: str = "",
    ) -> int:
        """Insert a confirmed correction and update aggregate stats.

        Returns the row id of the new corrections record.
        """
        # Insert the log row, update aggregate stats, and check promotion all in
        # one transaction so a crash can't leave the stats out of sync with the
        # log. `with self._conn` commits on success and rolls back on error.
        with self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO corrections
                  (script, original_sequence, corrected_sequence,
                   context_before, context_after, source_document,
                   reviewer_id, timestamp, confidence_delta, rule_applied)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    script,
                    original_sequence,
                    corrected_sequence,
                    context_before[:10],
                    context_after[:10],
                    source_document,
                    reviewer_id,
                    datetime.now(timezone.utc).isoformat(),
                    confidence_delta,
                    rule_applied,
                ),
            )
            row_id = cur.lastrowid

            self._conn.execute(
                """
                INSERT INTO correction_stats (script, original_sequence, corrected_sequence, count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(script, original_sequence, corrected_sequence)
                DO UPDATE SET count = count + 1
                """,
                (script, original_sequence, corrected_sequence),
            )

            self._maybe_promote(script, original_sequence, corrected_sequence)

        return row_id  # type: ignore[return-value]

    def _maybe_promote(
        self,
        script: str,
        original_sequence: str,
        corrected_sequence: str,
    ) -> None:
        """Promote a pair once it reaches the confirmation threshold.

        Must be called inside an open transaction (no commit here); the caller's
        ``with self._conn`` block commits the read-modify-write atomically.
        """
        row = self._conn.execute(
            """
            SELECT count, promoted FROM correction_stats
            WHERE script = ? AND original_sequence = ? AND corrected_sequence = ?
            """,
            (script, original_sequence, corrected_sequence),
        ).fetchone()

        if row and row["count"] >= _PROMOTION_THRESHOLD and not row["promoted"]:
            self._conn.execute(
                """
                UPDATE correction_stats SET promoted = 1
                WHERE script = ? AND original_sequence = ? AND corrected_sequence = ?
                """,
                (script, original_sequence, corrected_sequence),
            )
            logger.info(
                "Promoted correction: %r -> %r for script %r",
                original_sequence, corrected_sequence, script,
            )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_promoted_corrections(self, script: str) -> list[dict[str, Any]]:
        """Return all corrections that have been promoted for *script*."""
        rows = self._conn.execute(
            """
            SELECT original_sequence, corrected_sequence, count
            FROM correction_stats
            WHERE script = ? AND promoted = 1
            ORDER BY count DESC
            """,
            (script,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_promoted_pairs(self, script: str) -> list[tuple[str, str]]:
        """Return promoted corrections as ``(original, corrected)`` tuples.

        This is the legacy form :class:`~gurmukhifix.corrector.CharacterCorrector`
        consumes to apply corpus-learned, human-confirmed corrections. Prefer
        :meth:`get_promoted_rules`, which also carries the confirmed context.
        """
        return [
            (row["original_sequence"], row["corrected_sequence"])
            for row in self.get_promoted_corrections(script)
        ]

    def get_promoted_rules(self, script: str) -> list[dict[str, Any]]:
        """Return promoted corrections with their most common confirmed context.

        Each rule is ``{original_sequence, corrected_sequence, context_before,
        context_after}``. The context is the surrounding text that most frequently
        accompanied the confirmed correction; the corrector uses it to scope a
        same-validity correction to where a human actually saw it, rather than
        rewriting every occurrence globally.
        """
        rules: list[dict[str, Any]] = []
        for row in self.get_promoted_corrections(script):
            orig, corr = row["original_sequence"], row["corrected_sequence"]
            ctx = self._conn.execute(
                """
                SELECT context_before, context_after, COUNT(*) AS n
                FROM corrections
                WHERE script = ? AND original_sequence = ? AND corrected_sequence = ?
                GROUP BY context_before, context_after
                ORDER BY n DESC
                LIMIT 1
                """,
                (script, orig, corr),
            ).fetchone()
            rules.append(
                {
                    "original_sequence": orig,
                    "corrected_sequence": corr,
                    "context_before": (ctx["context_before"] if ctx else "") or "",
                    "context_after": (ctx["context_after"] if ctx else "") or "",
                }
            )
        return rules

    def get_stats(self, script: str | None = None) -> list[dict[str, Any]]:
        """Return aggregate correction statistics."""
        if script:
            rows = self._conn.execute(
                "SELECT * FROM correction_stats WHERE script = ? ORDER BY count DESC",
                (script,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM correction_stats ORDER BY count DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_corrections(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent corrections."""
        rows = self._conn.execute(
            "SELECT * FROM corrections ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def generate_report(self, script: str) -> dict[str, Any]:
        """Generate a report of correction statistics for *script*."""
        stats = self.get_stats(script)
        promoted = self.get_promoted_corrections(script)
        total = sum(s["count"] for s in stats)
        return {
            "script": script,
            "total_corrections": total,
            "unique_patterns": len(stats),
            "promoted_patterns": len(promoted),
            "top_corrections": stats[:20],
            "promoted_corrections": promoted,
        }

    # ------------------------------------------------------------------
    # Context extraction helper
    # ------------------------------------------------------------------

    @staticmethod
    def extract_context(text: str, position: int, window: int = 10) -> tuple[str, str]:
        """Extract context window around *position* in *text*."""
        before = text[max(0, position - window) : position]
        after = text[position : position + window]
        return before, after

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> "CorrectionStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


# Fallback schema if schema.sql is not found
_FALLBACK_SCHEMA = """
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
CREATE INDEX IF NOT EXISTS idx_stats_script_orig ON correction_stats(script, original_sequence);
"""
