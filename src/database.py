import sqlite3
import csv
from pathlib import Path
from typing import Any
from collections.abc import Iterator


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Create and return a database connection with row factory."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path) -> None:
    """Initialize database schema if tables don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS circles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_alt TEXT,
                twitter_id TEXT UNIQUE,
                twitter_id_alt TEXT,
                twitter_url TEXT,
                pixiv_url TEXT,
                identifier TEXT,
                author TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_circles_twitter_id ON circles(twitter_id);
            CREATE INDEX IF NOT EXISTS idx_circles_twitter_id_alt ON circles(twitter_id_alt);
            CREATE INDEX IF NOT EXISTS idx_circles_name ON circles(name);

            CREATE TABLE IF NOT EXISTS comike_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                booth TEXT,
                circle_name TEXT NOT NULL,
                author TEXT,
                notes TEXT,
                merged TEXT,
                detail_url TEXT,
                color TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_comike_event ON comike_info(event_name);
            CREATE INDEX IF NOT EXISTS idx_comike_circle ON comike_info(circle_name);
            CREATE INDEX IF NOT EXISTS idx_comike_booth ON comike_info(booth);
        """
        )
        conn.commit()


def migrate_csv_to_db(csv_path: Path, db_path: Path) -> int:
    """Migrate illustrator database CSV to SQLite. Returns number of rows imported."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    init_db(db_path)

    with get_connection(db_path) as conn:
        rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
        count = 0

        for row in rows:
            # Map CSV columns to DB fields
            name = row.get("社团（默认）", "").strip()
            if not name:
                continue

            conn.execute(
                """
                INSERT OR REPLACE INTO circles (
                    name, name_alt, twitter_id, twitter_id_alt,
                    twitter_url, pixiv_url, identifier, author
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    row.get("社团（备用）", "").strip() or None,
                    row.get("推特ID", "").strip().lower() or None,
                    row.get("推特ID（备用）", "").strip().lower() or None,
                    row.get("推特", "").strip() or None,
                    row.get("pixiv", "").strip() or None,
                    row.get("标识符", "").strip() or None,
                    row.get("作者", "").strip() or None,
                ),
            )
            count += 1

        conn.commit()
        print(f"[OK] Migrated {count} rows from {csv_path.name} to {db_path.name}")
        return count


def import_comike_info(csv_path: Path, db_path: Path, event_name: str) -> int:
    """Import Comike Info CSV into comike_info table. Returns row count."""
    init_db(db_path)

    with get_connection(db_path) as conn:
        rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
        count = 0

        for row in rows:
            booth = row.get("摊位", "").strip() or None
            circle_name = row.get("社团", "").strip()
            if not circle_name:
                continue

            notes = row.get("备注", "").strip() or None
            merged = row.get("合并", "").strip() or None
            detail_url = row.get("社团详情", "").strip() or None
            color = row.get("颜色", "").strip() or None
            author = row.get("作者", "").strip() or None

            conn.execute(
                """
                INSERT INTO comike_info (
                    event_name, booth, circle_name, author, notes,
                    merged, detail_url, color
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_name, booth, circle_name, author, notes, merged, detail_url, color),
            )
            count += 1

        conn.commit()
        print(f"[OK] Imported {count} comike info rows for {event_name}")
        return count


def query_circle_by_twitter_id(db_path: Path, twitter_id: str) -> dict[str, Any] | None:
    """Query circle info by twitter ID (primary or alt)."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT * FROM circles
            WHERE LOWER(twitter_id) = ? OR LOWER(twitter_id_alt) = ?
            LIMIT 1
            """,
            (twitter_id.lower(), twitter_id.lower()),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def query_circle_by_name(db_path: Path, name: str) -> dict[str, Any] | None:
    """Query circle info by circle name."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM circles WHERE name = ? OR name_alt = ? LIMIT 1",
            (name, name),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def query_comike_info(db_path: Path, event_name: str) -> Iterator[dict[str, Any]]:
    """Query all comike info rows for a given event."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM comike_info WHERE event_name = ? ORDER BY id",
            (event_name,),
        )
        for row in cursor:
            yield dict(row)


def get_latest_comike_event(db_path: Path) -> str | None:
    """Get the most recent event name from comike_info."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT event_name FROM comike_info
            GROUP BY event_name
            ORDER BY MAX(imported_at) DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        return row["event_name"] if row else None


def get_circle_to_booth_map(db_path: Path, event_name: str) -> dict[str, str]:
    """Build a mapping of circle_name -> booth for a given event."""
    map_: dict[str, str] = {}
    for row in query_comike_info(db_path, event_name):
        name = row.get("circle_name")
        booth = row.get("booth")
        if name and booth:
            map_[name] = booth
    return map_


def get_all_booths_for_event(db_path: Path, event_name: str) -> set[str]:
    """Get all unique booth numbers for an event."""
    booths: set[str] = set()
    for row in query_comike_info(db_path, event_name):
        booth = row.get("booth")
        if booth:
            booths.add(booth.strip())
    return booths


def get_remaining_circles(
    db_path: Path, event_name: str, existing_booths: set[str]
) -> Iterator[dict[str, Any]]:
    """Yield circles from comike_info that don't have matching shinagaki files."""
    for row in query_comike_info(db_path, event_name):
        booth = row.get("booth", "").strip() if row.get("booth") else ""
        if not booth:
            continue
        if booth in existing_booths:
            continue
        yield row


def enrich_with_db_links(
    rows: Iterator[dict[str, Any]], db_path: Path
) -> list[dict[str, Any]]:
    """Enrich comike info rows with database links (twitter URL)."""
    result = []
    for row in rows:
        circle_name = row.get("circle_name", "").strip()
        db_row = query_circle_by_name(db_path, circle_name) if circle_name else None
        row["数据库链接"] = db_row.get("twitter_url", "") if db_row else ""
        result.append(row)
    return result
