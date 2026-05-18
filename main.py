import os
import argparse
import asyncio
from collections import defaultdict

from src.utils import load_config, get_path
from src.core import extract_booth_from_filename
from src.database import (
    migrate_csv_to_db,
    init_db,
    get_remaining_circles,
    enrich_with_db_links,
)
from src.report import generate_html_report

def run_monitor(config):
    """Run progress monitoring logic using SQLite database."""
    # 1. Get config paths
    db_path = get_path(config, "paths.database")
    event_name = config.get("event_name", "C107")
    shinagaki_dir = get_path(config, "paths.shinagaki_dir")
    output_dir = get_path(config, "paths.output_dir")
    target_colors = config.get("filters", {}).get("target_colors", [])

    if not db_path or not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}")
        print("[INFO] Run 'uv run python main.py migrate' first")
        return

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Scanning shinagaki directory: {shinagaki_dir}")

    # 2. Get existing booths from files
    existing_booths: set[str] = set()
    if shinagaki_dir.exists():
        for root, _, files in os.walk(shinagaki_dir):
            for fn in files:
                if not fn.lower().endswith((".jpg", ".png")):
                    continue
                booth = extract_booth_from_filename(fn)
                if booth:
                    existing_booths.add(booth.strip())
    print(f"[INFO] Existing booth count: {len(existing_booths)}")

    # 3. Get remaining circles from database
    remaining_iter = get_remaining_circles(db_path, event_name, existing_booths)
    print(f"[INFO] Event: {event_name}")

    # 4. Enrich with database links
    remaining = enrich_with_db_links(remaining_iter, db_path)
    print(f"[INFO] Remaining rows without shinagaki: {len(remaining)}")

    # 5. Group by color
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in remaining:
        color = (r.get("color") or "").strip() or "无颜色"
        groups[color].append(r)
    print(f"[INFO] Color group count: {len(groups)}")

    # 6. Generate HTML reports
    for color, rows in groups.items():
        if target_colors and color not in target_colors:
            continue
        generate_html_report(rows, color, output_dir)

def run_migrate(config):
    """Migrate CSV database to SQLite."""
    csv_path = get_path(config, "paths.csv_database")
    db_path = get_path(config, "paths.database")

    if not csv_path or not csv_path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}")
        print("[INFO] Place your illustrator database CSV at the path in config.yaml")
        return

    init_db(db_path)
    try:
        migrate_csv_to_db(csv_path, db_path)
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return

    # Also import existing Comike Info CSVs into database
    comike_dir = get_path(config, "paths.comike_info_dir")
    event_name = config.get("event_name", "C107")
    if comike_dir and comike_dir.exists():
        from src.core import get_latest_comike_info

        latest = get_latest_comike_info(comike_dir)
        if latest:
            try:
                from src.database import import_comike_info

                import_comike_info(latest, db_path, event_name)
            except Exception as e:
                print(f"[WARN] Failed to import comike info: {e}")


def main():
    parser = argparse.ArgumentParser(description="CMYGO automation tool")
    parser.add_argument(
        "action",
        choices=["monitor", "rename", "auto", "sync", "sync-debug", "migrate"],
        help=(
            "Action to run: monitor, rename, auto, sync, sync-debug, migrate"
        ),
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")

    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return

    if args.action == "migrate":
        run_migrate(config)
    elif args.action == "monitor":
        run_monitor(config)
    elif args.action == "rename":
        from src.rename import run_rename

        run_rename(config)
    elif args.action == "sync":
        from src.catalog_sync import run_catalog_sync

        asyncio.run(run_catalog_sync(config))
    elif args.action == "sync-debug":
        from src.catalog_sync import run_catalog_sync_debug

        asyncio.run(run_catalog_sync_debug(config))
    elif args.action == "auto":
        from src.rename import run_rename
        from src.catalog_sync import run_catalog_sync

        try:
            asyncio.run(run_catalog_sync(config))
        except Exception as e:
            print(f"[ERROR] sync failed: {e}")
            return
        try:
            run_rename(config)
        except Exception as e:
            print(f"[ERROR] rename failed: {e}")
            return
        try:
            run_monitor(config)
        except Exception as e:
            print(f"[ERROR] monitor failed: {e}")
            return

if __name__ == '__main__':
    main()
