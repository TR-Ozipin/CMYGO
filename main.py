import os
import argparse
from collections import defaultdict
from pathlib import Path

from src.utils import load_config, get_path
from src.core import get_latest_comike_info, load_csv_dicts, extract_booth_from_filename
from src.report import generate_html_report

def run_monitor(config):
    """
    运行进度监控逻辑
    """
    # 1. 获取配置路径
    db_path = get_path(config, 'paths.database')
    comike_dir = get_path(config, 'paths.comike_info_dir')
    shinagaki_dir = get_path(config, 'paths.shinagaki_dir')
    output_dir = get_path(config, 'paths.output_dir')
    target_colors = config.get('filters', {}).get('target_colors', [])

    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] 正在扫描品书目录: {shinagaki_dir}")
    
    # 2. 获取已存在的摊位
    existing_booths = set()
    if shinagaki_dir.exists():
        for root, _, files in os.walk(shinagaki_dir):
            for fn in files:
                if not fn.lower().endswith(('.jpg', '.png')):
                    continue
                booth = extract_booth_from_filename(fn)
                if booth:
                    existing_booths.add(booth.strip())
    print(f"[INFO] 已存在摊位数量: {len(existing_booths)}")

    # 3. 读取最新的 Comike_Info CSV
    comike_file = get_latest_comike_info(comike_dir)
    if not comike_file:
        print(f"[ERROR] 未找到 Comike_Info_*.csv 文件在 {comike_dir}")
        return
    print(f"[INFO] 使用 Info 文件: {comike_file.name}")
    comike_rows = load_csv_dicts(comike_file, encoding='utf-8-sig')

    # 4. 读取数据库 CSV
    if not db_path.exists():
        print(f"[ERROR] 未找到数据库文件: {db_path}")
        return
    db_rows = load_csv_dicts(db_path, encoding='utf-8-sig')
    print(f"[INFO] 数据库行数: {len(db_rows)}")

    # 建立数据库索引
    db_by_circle = {}
    for r in db_rows:
        key = r.get('社团（默认）', '').strip()
        if key and key not in db_by_circle:
            db_by_circle[key] = r

    # 5. 过滤出摊位不在 existing_booths 的 comike 行
    remaining = []
    for r in comike_rows:
        booth = r.get('摊位', '').strip()
        if not booth:
            continue
        if booth in existing_booths:
            continue
        remaining.append(r)
    print(f"[INFO] 剩余未存在摊位的行: {len(remaining)}")

    # 6. 匹配数据库获取数据库链接
    for r in remaining:
        circle = r.get('社团', '').strip()
        db_row = db_by_circle.get(circle)
        if db_row:
            r['数据库链接'] = db_row.get('推特', '').strip()
        else:
            r['数据库链接'] = ''

    # 7. 按颜色分组
    groups = defaultdict(list)
    for r in remaining:
        color = r.get('颜色', '').strip() or '无颜色'
        groups[color].append(r)
    print(f"[INFO] 按颜色分组数: {len(groups)}")

    # 8. 输出 HTML 文件
    for color, rows in groups.items():
        if target_colors and color not in target_colors:
            continue
        generate_html_report(rows, color, output_dir)

def main():
    parser = argparse.ArgumentParser(description="CMYGO 自动化工具")
    parser.add_argument('action', choices=['monitor', 'rename', 'auto', 'sync', 'sync-debug'], 
                       help="执行的操作: monitor(进度监控), rename(自动重命名), auto(全部执行), sync(同步收藏), sync-debug(调试模式)")
    parser.add_argument('--config', default='config.yaml', help="配置文件路径")
    
    args = parser.parse_args()
    
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"[ERROR] 加载配置失败: {e}")
        return

    if args.action == 'monitor':
        run_monitor(config)
    elif args.action == 'rename':
        from src.rename import run_rename
        run_rename(config)
    elif args.action == 'sync':
        from src.catalog_sync import run_catalog_sync
        run_catalog_sync(config)
    elif args.action == 'sync-debug':
        from src.catalog_sync import run_catalog_sync_debug
        run_catalog_sync_debug(config)
    elif args.action == 'auto':
        from src.rename import run_rename
        from src.catalog_sync import run_catalog_sync
        run_catalog_sync(config)  # 先同步最新收藏
        run_rename(config)  # 然后重命名
        run_monitor(config)  # 最后生成报告

if __name__ == '__main__':
    main()
