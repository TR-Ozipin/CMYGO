#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C106品书进度监控.py

功能:
- 从 `shinagaki_dir` 目录（包含子目录）中读取 jpg/png 文件名，提取文件名开头的 "摊位"（第一个空格之前的部分）
- 加载最新的 Comike_Info_YYYY-MM-DD_HH-MM-SS.csv，并排除已存在摊位行
- 对剩下的行，用 Comike_Info 的 "社团" 去匹配 数据库 CSV 的 "社团（默认）" 列
  - 若匹配到，从数据库取 "推特" 列并作为该 comike 行的 "数据库链接"
- 按 "颜色" 列分组，为每种颜色生成一个 HTML 文件
  - 可筛选输出颜色 color-1 到 color-9
  - 每行固定列顺序 ['合并', '摊位', '社团', '作者', '备注', '数据库链接']
  - 省去 "颜色" 列
  - 将所有符合网页链接格式的文本渲染为超链接
  - 添加简单 CSS 样式
"""

import os
import csv
import re
from datetime import datetime
from collections import defaultdict

# ========== 用户可修改配置 ==========
# 数据库文件路径
database_path = r"C:\Users\Saline\OneDrive\文档\插画师数据库\插画师数据库 - 主表.csv"
# 存放 Comike_Info_*.csv 的目录
comike_info_dir = r"C:\Users\Saline\Downloads"
# 品书主文件夹路径（脚本递归遍历该目录及子目录中的 jpg/png 文件）
shinagaki_dir = r"C:\Users\Saline\OneDrive\C107品书"
# 输出 HTML 文件的路径
output_dir = r"C:\Users\Saline\Downloads\暂无品书列表"

# 想输出的颜色列表，例如 ['color-1', 'color-3']，留空 [] 表示全部颜色
# target_colors = ['color-1', 'color-2', 'color-3', 'color-4', 'color-5', 'color-6', 'color-7', 'color-8', 'color-9']
# target_colors = ['color-1', 'color-2', 'color-4', 'color-5', 'color-9']
target_colors = []
# ===================================

os.makedirs(output_dir, exist_ok=True)

def get_latest_comike_info(path):
    files = [f for f in os.listdir(path) if f.startswith("Comike_Info_") and f.endswith(".csv")]
    if not files:
        return None
    def keyname(x):
        try:
            ts = x.replace("Comike_Info_", "").replace(".csv", "")
            return datetime.strptime(ts, "%Y-%m-%d_%H-%M-%S")
        except Exception:
            return datetime.min
    files.sort(key=keyname, reverse=True)
    return os.path.join(path, files[0])

def load_csv_dicts(path, encoding='utf-8'):
    with open(path, newline='', encoding=encoding) as f:
        reader = csv.DictReader(f)
        return list(reader)

def extract_booth_from_filename(filename):
    base = os.path.splitext(filename)[0].strip()
    if not base:
        return None
    return base.split()[0]

_url_re = re.compile(r'(https?://[^\s"\'<>]+)')
def linkify(text):
    if text is None:
        return ''
    esc = (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
    return _url_re.sub(r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', esc)

def main():
    # 1) 获取已存在的摊位（遍历 shinagaki_dir 及子目录，只处理 jpg/png）
    existing_booths = set()
    if os.path.isdir(shinagaki_dir):
        for root, _, files in os.walk(shinagaki_dir):
            for fn in files:
                if not fn.lower().endswith(('.jpg', '.png')):
                    continue
                booth = extract_booth_from_filename(fn)
                if booth:
                    existing_booths.add(booth.strip())
    print(f"[INFO] 已存在摊位数量: {len(existing_booths)}")

    # 2) 读取最新的 Comike_Info CSV
    comike_file = get_latest_comike_info(comike_info_dir)
    if not comike_file:
        print("[ERROR] 未找到 Comike_Info_*.csv 文件")
        return
    print(f"[INFO] 使用文件: {comike_file}")
    comike_rows = load_csv_dicts(comike_file, encoding='utf-8-sig')

    # 3) 读取数据库 CSV
    if not os.path.exists(database_path):
        print("[ERROR] 未找到数据库文件")
        return
    db_rows = load_csv_dicts(database_path, encoding='utf-8-sig')
    print(f"[INFO] 数据库行数: {len(db_rows)}")

    db_by_circle = {}
    for r in db_rows:
        key = r.get('社团（默认）', '').strip()
        if key and key not in db_by_circle:
            db_by_circle[key] = r

    # 4) 过滤出摊位不在 existing_booths 的 comike 行
    remaining = []
    for r in comike_rows:
        booth = r.get('摊位', '').strip()
        if not booth:
            continue
        if booth in existing_booths:
            continue
        remaining.append(r)
    print(f"[INFO] 剩余未存在摊位的行: {len(remaining)}")

    # 5) 匹配数据库获取数据库链接
    for r in remaining:
        circle = r.get('社团', '').strip()
        db_row = db_by_circle.get(circle)
        if db_row:
            r['数据库链接'] = db_row.get('推特', '').strip()
        else:
            r['数据库链接'] = ''

    # 6) 按颜色分组
    groups = defaultdict(list)
    for r in remaining:
        color = r.get('颜色', '').strip() or '无颜色'
        groups[color].append(r)
    print(f"[INFO] 按颜色分组数: {len(groups)}")

    fixed_order = ['合并', '摊位', '社团', '作者', '备注', '数据库链接']

    # 7) 输出 HTML 文件
    for color, rows in groups.items():
        # 颜色筛选
        if target_colors and color not in target_colors:
            continue

        out_name = f"暂无品书列表{color}.html"
        out_path = os.path.join(output_dir, out_name)

        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n')
            title = f"{color} - Comike 列表"
            f.write(f"<title>{title}</title>\n")
            # CSS 样式
            f.write("""
        <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #fafafa; }
        a { color: #0645ad; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .button-link {
            display: inline-block;
            padding: 4px 8px;
            background-color: #4CAF50;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-size: 13px;
        }
        .button-link:hover {
            background-color: #45a049;
        }
        </style>
        """)
            f.write('</head>\n<body>\n')
            f.write(f"<h1>{title}</h1>\n")
            f.write('<table>\n')
            # 表头：新增“详情”列在最前面
            f.write('<tr><th>详情</th>')
            for h in fixed_order:
                f.write(f"<th>{h}</th>")
            f.write('</tr>\n')

            for rr in rows:
                f.write('<tr>')
                # 新增按钮列
                detail_url = rr.get('社团详情', '').strip()
                if detail_url.startswith('http'):
                    f.write(f'<td><a class="button-link" href="{detail_url}" target="_blank">查看</a></td>')
                else:
                    f.write('<td>-</td>')
                # 其他固定列
                for h in fixed_order:
                    val = rr.get(h, '')
                    html_val = linkify(val)
                    f.write(f"<td>{html_val}</td>")
                f.write('</tr>\n')

            f.write('</table>\n</body>\n</html>\n')

        print(f"[OK] 写出 HTML: {out_path} (行数: {len(rows)})")

if __name__ == '__main__':
    main()
