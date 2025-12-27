import os
import csv
import re
import shutil
from datetime import datetime
from collections import defaultdict

# ========== 用户可修改配置 ==========
def extract_twitter_id(filename):
    """
    从文件名中提取 twitter_id 的方法
    修改此处正则或解析逻辑即可适配不同文件名格式
    """
    #match = re.search(r'twitter-([^-]+)-\d+-\d+-\d{4}\.\d{2}\.\d{2}', filename)
    match = re.search(r'twitter-([^-]+)-\d+-\d{4}\.\d{2}\.\d{2}', filename)

    if match:
        return match.group(1).lower()
    return None

# 数据库文件路径
database_path = r"C:\Users\Saline\OneDrive\文档\插画师数据库\插画师数据库 - 主表.csv"
# 存放Comike_Info_*.csv的目录
comike_info_dir = r"C:\Users\Saline\Downloads"
# 未处理品书保存目录，存放重命名后的文件与原名备份文件的子目录
shinagaki_dir = r"C:\Users\Saline\OneDrive\C107品书"
processed_dir = os.path.join(shinagaki_dir, '已处理')
backup_dir = os.path.join(shinagaki_dir, '原名备份')
# ===================================

# Create necessary directories
os.makedirs(processed_dir, exist_ok=True)
os.makedirs(backup_dir, exist_ok=True)

# Get the latest Comike_Info_*.csv file by timestamp
def get_latest_comike_info(path):
    files = [f for f in os.listdir(path) if f.startswith("Comike_Info_") and f.endswith(".csv")]
    if not files:
        return None
    files.sort(
        key=lambda x: datetime.strptime(
            x.replace("Comike_Info_", "").replace(".csv", ""),
            "%Y-%m-%d_%H-%M-%S"
        ),
        reverse=True
    )
    return os.path.join(path, files[0])

comike_info_file = get_latest_comike_info(comike_info_dir)
if not comike_info_file:
    raise FileNotFoundError("No Comike_Info_*.csv file found")

# Load CSV into list of dicts
def load_csv_to_dictlist(path):
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

database_rows = load_csv_to_dictlist(database_path)
comike_info_rows = load_csv_to_dictlist(comike_info_file)

# Circle name -> booth mapping
circle_to_booth = {row['社团']: row['摊位'] for row in comike_info_rows}

# 非法字符替换为全角
def replace_illegal_chars(name):
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

# Step 1: Collect files by twitter_id
twitter_id_to_files = defaultdict(list)

for filename in os.listdir(shinagaki_dir):
    filepath = os.path.join(shinagaki_dir, filename)
    if not os.path.isfile(filepath):
        continue

    twitter_id = extract_twitter_id(filename)
    if not twitter_id:
        continue

    twitter_id_to_files[twitter_id].append(filename)

# Step 2: Process files grouped by twitter_id
for twitter_id, filenames in twitter_id_to_files.items():
    filenames.sort()  # 保证顺序一致（按文件名排序）

    # Step 2.1: 在数据库匹配（推特ID 或 推特ID（备用））
    matched_row = next(
        (
            row for row in database_rows
            if row.get('推特ID', '').lower() == twitter_id
            or row.get('推特ID（备用）', '').lower() == twitter_id
        ),
        None
    )

    if not matched_row:
        # Step 2.2: 匹配不到时，检查备注列是否包含“.com/推特ID”（不区分大小写）
        search_key = f".com/{twitter_id}"
        matched_comike_row = next(
            (row for row in comike_info_rows if search_key.lower() in row.get('备注', '').lower()),
            None
        )

        if matched_comike_row:
            merge_name = matched_comike_row.get('合并', '').strip()
            for idx, filename in enumerate(filenames):
                file_ext = os.path.splitext(filename)[1]
                base_name = replace_illegal_chars(merge_name)
                if len(filenames) > 1:
                    new_name = f"{base_name}-{idx + 1}{file_ext}"
                else:
                    new_name = f"{base_name}{file_ext}"

                src_path = os.path.join(shinagaki_dir, filename)
                dst_path = os.path.join(processed_dir, new_name)

                if not os.path.exists(dst_path):
                    shutil.copy2(src_path, dst_path)
                    print(f"[备注匹配] {filename} -> {new_name}")
                
                filename = filename.replace("twitter", base_name)
                shutil.move(src_path, os.path.join(backup_dir, filename))
        else:
            # print(f"[!] Twitter ID not found in database or comike_info: {twitter_id}")
            pass
        continue

    # 提取数据库信息
    circle_default = matched_row.get('社团（默认）', '').strip()
    circle_priority = matched_row.get('社团（优先）', '').strip()
    author_default = matched_row.get('作者（默认）', '').strip()
    author_priority = matched_row.get('作者（优先）', '').strip()
    identifier = matched_row.get('标识符', '').strip()

    if circle_priority or author_priority:
        print(f"[Info] Priority info for Twitter ID '{twitter_id}':")
        if circle_priority:
            print(f"  - Circle (priority): {circle_priority}")
        if author_priority:
            print(f"  - Author (priority): {author_priority}")

    booth = circle_to_booth.get(circle_default, '').strip()
    if not booth:
        print(f"[!] 无摊位信息: {circle_default} 尝试备注匹配")
                # Step 2.2: 匹配不到时，检查备注列是否包含“.com/推特ID”（不区分大小写）
        search_key = f".com/{twitter_id}"
        matched_comike_row = next(
            (row for row in comike_info_rows if search_key.lower() in row.get('备注', '').lower()),
            None
        )

        if matched_comike_row:
            merge_name = matched_comike_row.get('合并', '').strip()
            for idx, filename in enumerate(filenames):
                file_ext = os.path.splitext(filename)[1]
                base_name = replace_illegal_chars(merge_name)
                if len(filenames) > 1:
                    new_name = f"{base_name}-{idx + 1}{file_ext}"
                else:
                    new_name = f"{base_name}{file_ext}"

                src_path = os.path.join(shinagaki_dir, filename)
                dst_path = os.path.join(processed_dir, new_name)

                if not os.path.exists(dst_path):
                    shutil.copy2(src_path, dst_path)
                    print(f"[备注匹配] {filename} -> {new_name}")
                
                filename = filename.replace("twitter", base_name)
                shutil.move(src_path, os.path.join(backup_dir, filename))
        else:
            # print(f"[!] Twitter ID not found in database or comike_info: {twitter_id}")
            pass
        continue

    # Step 3: Rename and copy files with optional numbering
    for idx, filename in enumerate(filenames):
        file_ext = os.path.splitext(filename)[1]
        base_name = replace_illegal_chars(f"{booth} {identifier}")
        if len(filenames) > 1:
            numbered_name = f"{base_name}-{idx + 1}{file_ext}"
        else:
            numbered_name = f"{base_name}{file_ext}"

        src_path = os.path.join(shinagaki_dir, filename)
        dst_path = os.path.join(processed_dir, numbered_name)

        if not os.path.exists(dst_path):
            shutil.copy2(src_path, dst_path)
            print(f"[数据库匹配] {filename} -> {numbered_name}")

        filename = filename.replace("twitter", base_name)
        shutil.move(src_path, os.path.join(backup_dir, filename))
