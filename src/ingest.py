"""Ingest captured shinagaki from Chrome extension downloads.

Scans the ingest directory (default ~/Downloads/cmygo/) for JSON metadata
files created by the CMYGO Capture extension, copies images to shinagaki_dir,
and records metadata in the SQLite captures table.
"""

import json
import logging
import platform
import shutil
from pathlib import Path

from src.database import get_connection, init_db, save_capture
from src.utils import get_path
from src.vision import compute_image_hash

logger = logging.getLogger(__name__)


def _default_ingest_dir() -> Path:
    """Return the platform-appropriate default ingest directory."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Downloads" / "cmygo"
    elif system == "Windows":
        return Path.home() / "Downloads" / "cmygo"
    else:
        return Path.home() / "Downloads" / "cmygo"


def _resolve_ingest_dir(config: dict) -> Path:
    """Get the ingest directory from config or default."""
    raw = config.get("ingest", {}).get("dir", "")
    if raw:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = Path.cwd() / p
        return p
    return _default_ingest_dir()


def run_ingest(config: dict) -> int:
    """Ingest captured shinagaki images and metadata into CMYGO.

    Returns the number of images successfully ingested.
    """
    # 1. Resolve paths
    ingest_dir = _resolve_ingest_dir(config)
    shinagaki_dir = get_path(config, "paths.shinagaki_dir")
    db_path = get_path(config, "paths.database")
    do_archive = config.get("ingest", {}).get("archive", True)

    if not ingest_dir.exists():
        logger.info("Ingest directory does not exist: %s (nothing to ingest)", ingest_dir)
        return 0

    if not db_path or not db_path.exists():
        logger.info("Database not found, initializing: %s", db_path)
        init_db(db_path)

    # Ensure shinagaki dir exists
    shinagaki_dir.mkdir(parents=True, exist_ok=True)

    # Archive directory
    archive_dir = ingest_dir / "archived"
    if do_archive:
        archive_dir.mkdir(parents=True, exist_ok=True)

    # 2. Find all JSON metadata files
    json_files = sorted(ingest_dir.glob("*.json"))
    if not json_files:
        logger.info("No metadata files found in %s", ingest_dir)
        return 0

    logger.info("Found %d metadata files in %s", len(json_files), ingest_dir)

    total_ingested = 0

    # 3. Process each metadata file
    for json_path in json_files:
        try:
            with open(json_path, encoding="utf-8") as f:
                metadata = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping invalid metadata file %s: %s", json_path.name, e)
            continue

        twitter_id = metadata.get("twitter_id", "")
        tweet_url = metadata.get("tweet_url", "")
        tweet_text = metadata.get("tweet_text", "")
        captured_at = metadata.get("captured_at", "")
        image_filenames = metadata.get("image_filenames", [])

        if not twitter_id:
            logger.warning("Skipping %s: missing twitter_id", json_path.name)
            continue

        # Check if already ingested (by tweet_url)
        if tweet_url:
            existing = _check_existing_capture(db_path, tweet_url)
            if existing:
                logger.debug("Already ingested: %s", tweet_url)
                # Still archive the files
                if do_archive:
                    _archive_file(json_path, archive_dir)
                    for img_name in image_filenames:
                        img_path = ingest_dir / img_name
                        if img_path.exists():
                            _archive_file(img_path, archive_dir)
                continue

        # Process each image
        images_ok = 0
        for img_name in image_filenames:
            img_path = ingest_dir / img_name
            if not img_path.exists():
                logger.warning("Image not found: %s", img_path)
                continue

            # Copy to shinagaki directory
            dst_path = shinagaki_dir / img_name
            if not dst_path.exists():
                shutil.copy2(img_path, dst_path)
                logger.info("Ingested: %s -> %s", img_name, shinagaki_dir.name)
            else:
                logger.debug("Already exists in shinagaki dir: %s", img_name)

            # Compute image hash for cache key
            image_hash = compute_image_hash(img_path)

            # Save capture record
            save_capture(
                db_path,
                twitter_id=twitter_id,
                tweet_url=tweet_url,
                tweet_text=tweet_text,
                image_filename=img_name,
                image_hash=image_hash,
                captured_at=captured_at,
            )

            images_ok += 1

            # Archive the image
            if do_archive:
                _archive_file(img_path, archive_dir)

        # Archive the JSON
        if do_archive:
            _archive_file(json_path, archive_dir)

        if images_ok > 0:
            logger.info(
                "Captured @%s: %d images (tweet: %s)",
                twitter_id,
                images_ok,
                tweet_url[:60] + "..." if len(tweet_url) > 60 else tweet_url,
            )
            total_ingested += images_ok

    logger.info("Ingest complete: %d images ingested", total_ingested)
    return total_ingested


def _check_existing_capture(db_path: Path, tweet_url: str) -> bool:
    """Check if a tweet has already been captured."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM captures WHERE tweet_url = ? LIMIT 1",
            (tweet_url,),
        ).fetchone()
        return row is not None


def _archive_file(src: Path, archive_dir: Path) -> None:
    """Move a file to the archive directory."""
    dst = archive_dir / src.name
    if dst.exists():
        # If already archived, just remove the source
        src.unlink()
    else:
        shutil.move(str(src), str(dst))
