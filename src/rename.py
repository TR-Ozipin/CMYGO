import logging
import shutil
import re
from collections import defaultdict
from pathlib import Path

from src.utils import get_path
from src.database import (
    query_circle_by_twitter_id,
    get_circle_to_booth_map,
    get_vision_cache,
    save_vision_cache,
    query_comike_info,
)

logger = logging.getLogger(__name__)


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


def _try_vision_match(
    files: list[Path],
    comike_rows: list[dict],
    circle_to_booth: dict[str, str],
    db_path: Path,
    vision_client,
    processed_dir: Path,
    backup_dir: Path,
) -> list[Path]:
    """Try Vision LLM recognition on files. Returns list of still-unmatched files."""
    from src.vision import compute_image_hash

    unmatched = []

    for src_path in files:
        # Check cache first
        image_hash = compute_image_hash(src_path)
        cached = get_vision_cache(db_path, image_hash)

        if cached:
            result = cached
            logger.debug("Vision cache hit for %s", src_path.name)
        else:
            logger.info("Running Vision recognition on: %s", src_path.name)
            result = vision_client.recognize(src_path)
            if result:
                save_vision_cache(db_path, image_hash, result)

        if not result:
            unmatched.append(src_path)
            continue

        # Check confidence
        if not vision_client.is_above_threshold(result):
            logger.warning(
                "Low confidence (%.2f) for %s, marking as unrecognized",
                result.get("confidence", 0.0),
                src_path.name,
            )
            unmatched.append(src_path)
            continue

        # Try to match using recognized data
        recognized_name = _match_vision_result(
            result, comike_rows, circle_to_booth, db_path
        )
        if recognized_name:
            _process_files(
                [src_path], recognized_name, processed_dir, backup_dir, "Vision识别"
            )
        else:
            logger.warning(
                "Vision recognized but no DB match for %s (booth=%s, circle=%s)",
                src_path.name,
                result.get("booth"),
                result.get("circle_name"),
            )
            unmatched.append(src_path)

    return unmatched


def _match_vision_result(
    result: dict,
    comike_rows: list[dict],
    circle_to_booth: dict[str, str],
    db_path: Path,
) -> str | None:
    """Try to match vision recognition result against database.

    Returns the base filename string (e.g., "booth identifier") or None.
    """
    # Strategy 1: Match by recognized twitter_id
    twitter_id = (result.get("twitter_id") or "").strip()
    if twitter_id:
        circle = query_circle_by_twitter_id(db_path, twitter_id)
        if circle:
            circle_name = (circle.get("name") or "").strip()
            identifier = (circle.get("identifier") or "").strip()
            booth = (circle_to_booth.get(circle_name) or "").strip()
            if booth:
                return f"{booth} {identifier}"

    # Strategy 2: Match by recognized circle_name against comike_info
    recognized_circle = (result.get("circle_name") or "").strip()
    if recognized_circle:
        for row in comike_rows:
            db_circle = (row.get("circle_name") or "").strip()
            if db_circle and db_circle == recognized_circle:
                merged = (row.get("merged") or "").strip()
                if merged:
                    return merged

    # Strategy 3: Match by recognized booth directly
    recognized_booth = (result.get("booth") or "").strip()
    if recognized_booth:
        for row in comike_rows:
            db_booth = (row.get("booth") or "").strip()
            if db_booth and db_booth == recognized_booth:
                merged = (row.get("merged") or "").strip()
                if merged:
                    return merged

    return None


def run_rename(config):
    """Run rename logic using SQLite database.

    Matching chain:
    1. Extract Twitter ID from filename -> query circles table
    2. Fallback: match by notes in comike_info
    3. Fallback: Vision LLM recognition (if enabled)
    4. If all fail: mark as unrecognized
    """
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
        logger.error("Database not found: %s", db_path)
        logger.info("Run 'uv run python main.py migrate' first to import CSV to SQLite")
        return

    processed_dir = shinagaki_dir / processed_name
    backup_dir = shinagaki_dir / backup_name

    # Create required directories
    processed_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Processing directory: %s", shinagaki_dir)
    logger.info("Loading database: %s", db_path.name)

    # 2. Build circle -> booth map from database
    circle_to_booth = get_circle_to_booth_map(db_path, event_name)

    # 3. Load comike info for fallback matching
    comike_rows = list(query_comike_info(db_path, event_name))

    # 4. Initialize Vision client (if enabled)
    from src.vision import create_client_from_config
    vision_client = create_client_from_config(config)
    if vision_client:
        logger.info(
            "Vision LLM enabled (model=%s, threshold=%.2f)",
            vision_client.model,
            vision_client.confidence_threshold,
        )

    # 5. Collect all image files
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    all_image_files: list[Path] = []
    for entry in shinagaki_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.name.startswith("."):
            continue
        if entry.suffix.lower() in image_extensions:
            all_image_files.append(entry)

    # 6. Group files by Twitter ID
    twitter_id_to_files: dict[str, list[Path]] = defaultdict(list)
    no_twitter_id_files: list[Path] = []

    for entry in all_image_files:
        twitter_id = extract_twitter_id(entry.name, twitter_pattern)
        if twitter_id:
            twitter_id_to_files[twitter_id].append(entry)
        else:
            no_twitter_id_files.append(entry)

    logger.info("Found %d Twitter ID file groups", len(twitter_id_to_files))
    if no_twitter_id_files:
        logger.info(
            "Found %d files without Twitter ID in filename",
            len(no_twitter_id_files),
        )

    # 7. Process Twitter ID groups (existing logic)
    vision_pending: list[Path] = []  # Files that failed Twitter ID + notes matching

    for twitter_id, files in twitter_id_to_files.items():
        files.sort(key=lambda x: x.name)

        # 7.1 Match by Twitter ID in database
        matched_row = query_circle_by_twitter_id(db_path, twitter_id)

        # 7.2 Fallback: match by notes in comike info
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
                _process_files(
                    files, merge_name, processed_dir, backup_dir, "备注匹配"
                )
            else:
                # Could not match — queue for Vision
                vision_pending.extend(files)
            continue

        # 7.3 Database match succeeded
        circle_name = (matched_row.get("name") or "").strip()
        identifier = (matched_row.get("identifier") or "").strip()

        # Get booth number
        booth = (circle_to_booth.get(circle_name) or "").strip()

        if not booth:
            logger.warning(
                "No booth info: %s (Twitter: %s) - trying fallback",
                circle_name, twitter_id,
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
            else:
                vision_pending.extend(files)
            continue

        # Build new filename base: "booth identifier"
        base_name_str = f"{booth} {identifier}"
        _process_files(files, base_name_str, processed_dir, backup_dir, "数据库匹配")

    # 8. Vision LLM fallback for unmatched files
    all_vision_candidates = vision_pending + no_twitter_id_files
    unrecognized: list[Path] = []

    if all_vision_candidates and vision_client:
        logger.info(
            "Running Vision LLM on %d unmatched files...",
            len(all_vision_candidates),
        )
        unrecognized = _try_vision_match(
            all_vision_candidates,
            comike_rows,
            circle_to_booth,
            db_path,
            vision_client,
            processed_dir,
            backup_dir,
        )
    elif all_vision_candidates:
        # Vision not enabled — all candidates are unrecognized
        unrecognized = all_vision_candidates
        if unrecognized:
            logger.info(
                "%d files could not be matched (Vision LLM disabled, "
                "enable in config.yaml to try recognition)",
                len(unrecognized),
            )

    # 9. Generate unrecognized report
    if unrecognized:
        _generate_unrecognized_report(unrecognized, shinagaki_dir)


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
            logger.info("[%s] %s -> %s", match_type, src_path.name, new_name)

        # 移动原文件到备份目录 (且重命名原文件，将twitter替换为社团名/标识符，方便识别)
        # 注意：原逻辑是 filename.replace("twitter", base_name)，这里保持一致
        # 但要注意 base_name 可能包含空格，而原文件名中 twitter-xxx 可能是紧凑的
        # 为了安全，简单替换
        backup_filename = src_path.name.replace("twitter", base_name)
        backup_path = backup_dir / backup_filename

        if not backup_path.exists():
            shutil.move(src_path, backup_path)


def _generate_unrecognized_report(files: list[Path], output_dir: Path) -> None:
    """Generate a simple HTML report of unrecognized shinagaki files."""
    report_path = output_dir / "未识别品书列表.html"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(
            '<!doctype html>\n<html lang="zh-CN">\n<head>\n'
            '<meta charset="utf-8">\n'
        )
        f.write("<title>未识別品书列表</title>\n")
        f.write("""
    <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    h1 { color: #c0392b; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
    th { background-color: #f2f2f2; }
    tr:nth-child(even) { background-color: #fafafa; }
    .count { color: #888; margin-bottom: 20px; }
    </style>
    """)
        f.write("</head>\n<body>\n")
        f.write("<h1>未識別品書列表</h1>\n")
        f.write(f'<p class="count">共 {len(files)} 个文件未能自动匹配</p>\n')
        f.write("<table>\n<tr><th>#</th><th>文件名</th><th>大小</th></tr>\n")

        for i, fp in enumerate(sorted(files, key=lambda x: x.name), 1):
            size_kb = fp.stat().st_size / 1024
            f.write(
                f"<tr><td>{i}</td><td>{fp.name}</td>"
                f"<td>{size_kb:.1f} KB</td></tr>\n"
            )

        f.write("</table>\n</body>\n</html>\n")

    logger.info("未识别品书报告: %s (%d files)", report_path, len(files))
