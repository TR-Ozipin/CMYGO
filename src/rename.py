import shutil
import re
from collections import defaultdict

from src.utils import get_path
from src.core import get_latest_comike_info, load_csv_dicts

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
    """
    运行重命名逻辑
    """
    # 1. 获取配置
    db_path = get_path(config, 'paths.database')
    comike_dir = get_path(config, 'paths.comike_info_dir')
    shinagaki_dir = get_path(config, 'paths.shinagaki_dir')
    backup_name = config.get('paths', {}).get('backup_subdir_name', '原名备份')
    processed_name = config.get('paths', {}).get('processed_subdir_name', '已处理')
    twitter_pattern = config.get('patterns', {}).get('twitter_id', r"twitter-([^-]+)-\d+-\d+")

    processed_dir = shinagaki_dir / processed_name
    backup_dir = shinagaki_dir / backup_name

    # 创建必要目录
    processed_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] 正在处理目录: {shinagaki_dir}")

    # 2. 读取数据
    if not comike_dir.exists():
        print(f"[ERROR] Comike Info 目录不存在: {comike_dir}")
        return
        
    comike_info_file = get_latest_comike_info(comike_dir)
    if not comike_info_file:
        print("[ERROR] 未找到 Comike_Info_*.csv 文件")
        return

    if not db_path.exists():
        print(f"[ERROR] 数据库文件不存在: {db_path}")
        return

    print(f"[INFO] 加载数据库: {db_path.name}")
    database_rows = load_csv_dicts(db_path)
    print(f"[INFO] 加载 Info: {comike_info_file.name}")
    comike_info_rows = load_csv_dicts(comike_info_file)

    # 3. 建立索引
    circle_to_booth = {row['社团']: row['摊位'] for row in comike_info_rows}

    # 4. 按 Twitter ID 分组文件
    twitter_id_to_files = defaultdict(list)
    for entry in shinagaki_dir.iterdir():
        if not entry.is_file():
            continue
        
        # 跳过隐藏文件
        if entry.name.startswith('.'):
            continue

        twitter_id = extract_twitter_id(entry.name, twitter_pattern)
        if not twitter_id:
            continue

        twitter_id_to_files[twitter_id].append(entry)

    print(f"[INFO] 找到 {len(twitter_id_to_files)} 个 Twitter ID 对应的文件组")

    # 5. 处理每个 Twitter ID 组
    for twitter_id, files in twitter_id_to_files.items():
        files.sort(key=lambda x: x.name)  # 保证顺序一致

        # 5.1 在数据库匹配
        matched_row = next(
            (
                row for row in database_rows
                if row.get('推特ID', '').lower() == twitter_id
                or row.get('推特ID（备用）', '').lower() == twitter_id
            ),
            None
        )

        # 5.2 匹配不到时，尝试备注匹配
        if not matched_row:
            search_key = f".com/{twitter_id}"
            matched_comike_row = next(
                (row for row in comike_info_rows if search_key.lower() in row.get('备注', '').lower()),
                None
            )

            if matched_comike_row:
                merge_name = matched_comike_row.get('合并', '').strip()
                # 执行备注匹配的重命名
                _process_files(files, merge_name, processed_dir, backup_dir, twitter_id, "备注匹配")
            else:
                # 确实找不到
                pass
            continue

        # 5.3 数据库匹配成功，提取信息
        circle_default = matched_row.get('社团（默认）', '').strip()
        identifier = matched_row.get('标识符', '').strip()
        
        # 获取摊位号
        booth = circle_to_booth.get(circle_default, '').strip()

        if not booth:
            print(f"[WARN] 无摊位信息: {circle_default} (Twitter: {twitter_id}) - 尝试备注匹配")
            # 再次尝试备注匹配作为回退
            search_key = f".com/{twitter_id}"
            matched_comike_row = next(
                (row for row in comike_info_rows if search_key.lower() in row.get('备注', '').lower()),
                None
            )
            if matched_comike_row:
                 merge_name = matched_comike_row.get('合并', '').strip()
                 _process_files(files, merge_name, processed_dir, backup_dir, twitter_id, "备注匹配(回退)")
            continue

        # 构造新文件名基底: "摊位号 标识符"
        base_name_str = f"{booth} {identifier}"
        _process_files(files, base_name_str, processed_dir, backup_dir, twitter_id, "数据库匹配")

def _process_files(files, base_name_raw, processed_dir, backup_dir, twitter_id, match_type):
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

