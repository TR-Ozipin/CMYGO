import shutil
import re
from collections import defaultdict
from pathlib import Path

from src.utils import get_path
from src.database import (
    query_circle_by_twitter_id,
    get_circle_to_booth_map,
    query_comike_info,
)

def replace_illegal_chars(name):
    """
    非法字符替换为全角
    """
    illegal_map = {
        '\\': '＼',
        '/': '／',
        ':': '：',
        '*': '＊',
        '?': '？',
        '"': '＂',
        '<': '＜',
        '>': '＞',
        '|': '｜'
    }
    for bad, full in illegal_map.items():
        name = name.replace(bad, full)
    return name

def extract_twitter_id(filename, pattern):
    """
    从文件名中提取 twitter_id
    """
    match = re.search(pattern, filename)
    if match:
        return match.group(1).lower()
    return None

def run_rename(config):
    """Run rename logic using SQLite database."""
    # 1. Get config
    db_path = get_path(config, "paths.database")
    event_name = config.get("event_name", "C107")
    shinagaki_dir = get_path(config, "paths.shinagaki_dir")
    backup_name = config.get("paths", {}).get("backup_subdir_name", "原名备份")
    processed_name = config.get("paths", {}).get("processed_subdir_name", "已处理")
    twitter_pattern = config.get("patterns", {}).get(
        "twitter_id", r"twitter-([^-]+)-\d+-\d+"
    )

    if not db_path or not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}")
        print("[INFO] Run 'uv run python main.py migrate' first to import CSV to SQLite")
        return

    processed_dir = shinagaki_dir / processed_name
    backup_dir = shinagaki_dir / backup_name

    # Create required directories
    processed_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Processing directory: {shinagaki_dir}")
    print(f"[INFO] Loading database: {db_path.name}")

    # 2. Build circle -> booth map from database
    circle_to_booth = get_circle_to_booth_map(db_path, event_name)

    # 3. Load comike info for fallback matching
    comike_rows = list(query_comike_info(db_path, event_name))

    # 4. Group files by Twitter ID
    twitter_id_to_files: dict[str, list[Path]] = defaultdict(list)
    for entry in shinagaki_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.name.startswith("."):
            continue

        twitter_id = extract_twitter_id(entry.name, twitter_pattern)
        if not twitter_id:
            continue

        twitter_id_to_files[twitter_id].append(entry)

    print(f"[INFO] Found {len(twitter_id_to_files)} Twitter ID file groups")

    # 5. Process each Twitter ID group
    for twitter_id, files in twitter_id_to_files.items():
        files.sort(key=lambda x: x.name)

        # 5.1 Match by Twitter ID in database
        matched_row = query_circle_by_twitter_id(db_path, twitter_id)

        # 5.2 Fallback: match by notes in comike info
        if not matched_row:
            search_key = f".com/{twitter_id}"
            matched_comike_row = next(
                (
                    row
                    for row in comike_rows
                    if row.get("notes")
                    and search_key.lower() in row["notes"].lower()
                ),
                None,
            )

            if matched_comike_row:
                merge_name = (matched_comike_row.get("merged") or "").strip()
                _process_files(files, merge_name, processed_dir, backup_dir, "备注匹配")
            continue

        # 5.3 Database match succeeded
        circle_name = (matched_row.get("name") or "").strip()
        identifier = (matched_row.get("identifier") or "").strip()

        # Get booth number
        booth = (circle_to_booth.get(circle_name) or "").strip()

        if not booth:
            print(
                f"[WARN] No booth info: {circle_name} (Twitter: {twitter_id})"
                f" - trying fallback"
            )
            search_key = f".com/{twitter_id}"
            matched_comike_row = next(
                (
                    row
                    for row in comike_rows
                    if row.get("notes")
                    and search_key.lower() in row["notes"].lower()
                ),
                None,
            )
            if matched_comike_row:
                merge_name = (matched_comike_row.get("merged") or "").strip()
                _process_files(
                    files, merge_name, processed_dir, backup_dir, "备注匹配(回退)"
                )
            continue

        # Build new filename base: "booth identifier"
        base_name_str = f"{booth} {identifier}"
        _process_files(files, base_name_str, processed_dir, backup_dir, "数据库匹配")

def _process_files(files, base_name_raw, processed_dir, backup_dir, match_type):
    """
    执行具体的文件复制和移动操作
    """
    base_name = replace_illegal_chars(base_name_raw)
    
    for idx, src_path in enumerate(files):
        file_ext = src_path.suffix
        
        # 构造目标文件名
        if len(files) > 1:
            new_name = f"{base_name}-{idx + 1}{file_ext}"
        else:
            new_name = f"{base_name}{file_ext}"
            
        dst_path = processed_dir / new_name

        # 复制到已处理
        if not dst_path.exists():
            shutil.copy2(src_path, dst_path)
            print(f"[{match_type}] {src_path.name} -> {new_name}")
        
        # 移动原文件到备份目录 (且重命名原文件，将twitter替换为社团名/标识符，方便识别)
        # 注意：原逻辑是 filename.replace("twitter", base_name)，这里保持一致
        # 但要注意 base_name 可能包含空格，而原文件名中 twitter-xxx 可能是紧凑的
        # 为了安全，简单替换
        backup_filename = src_path.name.replace("twitter", base_name)
        backup_path = backup_dir / backup_filename
        
        if not backup_path.exists():
            shutil.move(src_path, backup_path)

