"""Tests for the ingest pipeline."""

import json
from pathlib import Path

from src.database import init_db, get_connection, save_capture
from src.ingest import run_ingest


def _make_config(tmp_path: Path) -> dict:
    """Create a test config pointing to temp directories."""
    db_path = tmp_path / "test.db"
    shinagaki_dir = tmp_path / "shinagaki"
    ingest_dir = tmp_path / "cmygo_downloads"

    shinagaki_dir.mkdir()
    ingest_dir.mkdir()
    init_db(db_path)

    return {
        "paths": {
            "database": str(db_path),
            "shinagaki_dir": str(shinagaki_dir),
        },
        "ingest": {
            "dir": str(ingest_dir),
            "archive": True,
        },
    }


def _create_capture_files(
    ingest_dir: Path,
    twitter_id: str = "testuser",
    timestamp: int = 1716100200,
    num_images: int = 1,
) -> None:
    """Create fake capture JSON + image files in the ingest directory."""
    image_filenames = []
    for i in range(num_images):
        img_name = f"twitter-{twitter_id}-{timestamp}-{i + 1}.jpg"
        (ingest_dir / img_name).write_bytes(b"fake image content " + str(i).encode())
        image_filenames.append(img_name)

    metadata = {
        "twitter_id": twitter_id,
        "tweet_url": f"https://x.com/{twitter_id}/status/{timestamp}",
        "tweet_text": f"CM107 新刊情報！ {twitter_id}",
        "tweet_time": "2026-05-19T12:00:00Z",
        "images": num_images,
        "image_filenames": image_filenames,
        "captured_at": "2026-05-19T13:00:00+09:00",
    }

    json_path = ingest_dir / f"twitter-{twitter_id}-{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f)


class TestRunIngest:
    """Test the ingest pipeline end-to-end."""

    def test_basic_ingest(self, tmp_path):
        config = _make_config(tmp_path)
        ingest_dir = Path(config["ingest"]["dir"])
        shinagaki_dir = Path(config["paths"]["shinagaki_dir"])

        _create_capture_files(ingest_dir, "artist1", 1000001)

        result = run_ingest(config)
        assert result == 1

        # Check image was copied to shinagaki dir
        copied = list(shinagaki_dir.glob("*.jpg"))
        assert len(copied) == 1
        assert "artist1" in copied[0].name

        # Check original files were archived
        archived = list((ingest_dir / "archived").iterdir())
        assert len(archived) == 2  # 1 json + 1 image

    def test_multi_image_tweet(self, tmp_path):
        config = _make_config(tmp_path)
        ingest_dir = Path(config["ingest"]["dir"])

        _create_capture_files(ingest_dir, "artist2", 2000001, num_images=3)

        result = run_ingest(config)
        assert result == 3

        shinagaki_dir = Path(config["paths"]["shinagaki_dir"])
        assert len(list(shinagaki_dir.glob("*.jpg"))) == 3

    def test_no_duplicate_ingest(self, tmp_path):
        config = _make_config(tmp_path)
        ingest_dir = Path(config["ingest"]["dir"])

        _create_capture_files(ingest_dir, "artist3", 3000001)
        result1 = run_ingest(config)
        assert result1 == 1

        # Create same files again
        _create_capture_files(ingest_dir, "artist3", 3000001)
        result2 = run_ingest(config)
        assert result2 == 0  # Should skip (already ingested)

    def test_empty_ingest_dir(self, tmp_path):
        config = _make_config(tmp_path)
        result = run_ingest(config)
        assert result == 0

    def test_missing_ingest_dir(self, tmp_path):
        config = _make_config(tmp_path)
        config["ingest"]["dir"] = str(tmp_path / "nonexistent")
        result = run_ingest(config)
        assert result == 0


class TestSaveCapture:
    """Test the save_capture database function."""

    def test_save_and_query(self, tmp_path):
        db_path = tmp_path / "test.db"
        init_db(db_path)

        save_capture(
            db_path,
            twitter_id="testuser",
            tweet_url="https://x.com/testuser/status/123",
            tweet_text="Hello world",
            image_filename="test.jpg",
            image_hash="abc123",
            captured_at="2026-05-19T00:00:00Z",
        )

        conn = get_connection(db_path)
        rows = conn.execute("SELECT * FROM captures").fetchall()
        assert len(rows) == 1
        assert dict(rows[0])["twitter_id"] == "testuser"
        conn.close()

    def test_dedup_by_tweet_url_and_filename(self, tmp_path):
        db_path = tmp_path / "test.db"
        init_db(db_path)

        for _ in range(3):
            save_capture(
                db_path,
                twitter_id="user",
                tweet_url="https://x.com/user/status/1",
                tweet_text="text",
                image_filename="img.jpg",
                image_hash="hash",
                captured_at="now",
            )

        conn = get_connection(db_path)
        count = conn.execute("SELECT COUNT(*) FROM captures").fetchone()[0]
        conn.close()
        assert count == 1
