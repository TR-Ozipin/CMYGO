"""Tests for database functions using in-memory SQLite."""

import sqlite3
import csv
from pathlib import Path

from src.database import (
    init_db,
    migrate_csv_to_db,
    import_comike_info,
    query_circle_by_twitter_id,
)


def _create_temp_db(tmp_path: Path) -> Path:
    """Create and initialize a temporary database."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write a CSV file with given fieldnames and rows."""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestQueryCircleByTwitterId:
    """Test querying circles by Twitter ID."""

    def test_match_primary(self, tmp_path):
        db_path = _create_temp_db(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO circles (name, twitter_id, identifier) VALUES (?, ?, ?)",
            ("TestCircle", "testuser", "TC"),
        )
        conn.commit()
        conn.close()

        result = query_circle_by_twitter_id(db_path, "testuser")
        assert result is not None
        assert result["name"] == "TestCircle"

    def test_match_alt(self, tmp_path):
        db_path = _create_temp_db(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO circles (name, twitter_id, twitter_id_alt) VALUES (?, ?, ?)",
            ("TestCircle", "main_id", "alt_id"),
        )
        conn.commit()
        conn.close()

        result = query_circle_by_twitter_id(db_path, "alt_id")
        assert result is not None
        assert result["name"] == "TestCircle"

    def test_case_insensitive(self, tmp_path):
        db_path = _create_temp_db(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO circles (name, twitter_id) VALUES (?, ?)",
            ("TestCircle", "testuser"),
        )
        conn.commit()
        conn.close()

        result = query_circle_by_twitter_id(db_path, "TESTUSER")
        assert result is not None

    def test_no_match(self, tmp_path):
        db_path = _create_temp_db(tmp_path)
        result = query_circle_by_twitter_id(db_path, "nonexistent")
        assert result is None


class TestComikInfoDedup:
    """Test that duplicate comike_info rows are handled correctly."""

    def test_import_ignores_duplicates(self, tmp_path):
        db_path = _create_temp_db(tmp_path)

        # Create a CSV with some data
        csv_path = tmp_path / "test_comike.csv"
        _write_csv(
            csv_path,
            ["摊位", "社团", "作者", "备注", "合并", "社团详情", "颜色"],
            [
                {"摊位": "A01", "社团": "Circle1", "作者": "Author1",
                 "备注": "", "合并": "A01 Circle1", "社团详情": "", "颜色": "color-1"},
                {"摊位": "A02", "社团": "Circle2", "作者": "Author2",
                 "备注": "", "合并": "A02 Circle2", "社团详情": "", "颜色": "color-2"},
            ],
        )

        # Import twice
        import_comike_info(csv_path, db_path, "C107")
        import_comike_info(csv_path, db_path, "C107")

        # Should still only have 2 rows (not 4)
        conn = sqlite3.connect(str(db_path))
        count = conn.execute(
            "SELECT COUNT(*) FROM comike_info WHERE event_name = ?", ("C107",)
        ).fetchone()[0]
        conn.close()

        assert count == 2

    def test_different_events_not_deduped(self, tmp_path):
        db_path = _create_temp_db(tmp_path)

        csv_path = tmp_path / "test_comike.csv"
        _write_csv(
            csv_path,
            ["摊位", "社团", "作者", "备注", "合并", "社团详情", "颜色"],
            [
                {"摊位": "A01", "社团": "Circle1", "作者": "Author1",
                 "备注": "", "合并": "A01 Circle1", "社团详情": "", "颜色": "color-1"},
            ],
        )

        # Import for two different events
        import_comike_info(csv_path, db_path, "C107")
        import_comike_info(csv_path, db_path, "C108")

        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM comike_info").fetchone()[0]
        conn.close()

        assert count == 2


class TestMigrateCsv:
    """Test CSV migration to SQLite."""

    def test_basic_migration(self, tmp_path):
        db_path = _create_temp_db(tmp_path)

        csv_path = tmp_path / "test_circles.csv"
        _write_csv(
            csv_path,
            ["社团（默认）", "社团（备用）", "推特ID", "推特ID（备用）",
             "推特", "pixiv", "标识符", "作者"],
            [
                {"社团（默认）": "MyCircle", "社团（备用）": "", "推特ID": "mytwitter",
                 "推特ID（备用）": "", "推特": "https://twitter.com/mytwitter",
                 "pixiv": "", "标识符": "MC", "作者": "Author1"},
            ],
        )

        count = migrate_csv_to_db(csv_path, db_path)
        assert count == 1

        result = query_circle_by_twitter_id(db_path, "mytwitter")
        assert result is not None
        assert result["name"] == "MyCircle"
        assert result["identifier"] == "MC"
