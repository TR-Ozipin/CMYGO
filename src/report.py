import logging
import re

logger = logging.getLogger(__name__)

_url_re = re.compile(r'(https?://[^\s"\'<>]+)')

def linkify(text):
    """
    将文本中的 URL 转换为 HTML 链接
    """
    if text is None:
        return ''
    esc = (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
    return _url_re.sub(r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', esc)

def generate_html_report(rows, color, output_dir):
    """
    生成单个颜色的 HTML 报告
    """
    fixed_order = ['合并', '摊位', '社团', '作者', '备注', '数据库链接']
    
    out_name = f"暂无品书列表{color}.html"
    out_path = output_dir / out_name
    
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
    
    logger.info("写出 HTML: %s (行数: %d)", out_path, len(rows))

