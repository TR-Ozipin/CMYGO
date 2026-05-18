import csv
from datetime import datetime
from pathlib import Path

def get_latest_comike_info(path):
    """
    获取最新的 Comike_Info_*.csv 文件
    """
    path = Path(path)
    if not path.exists():
        return None
        
    files = [f for f in path.glob("Comike_Info_*.csv")]
    if not files:
        return None
        
    def keyname(x):
        try:
            ts = x.name.replace("Comike_Info_", "").replace(".csv", "")
            return datetime.strptime(ts, "%Y-%m-%d_%H-%M-%S")
        except Exception:
            return datetime.min
            
    files.sort(key=keyname, reverse=True)
    return files[0]

def load_csv_dicts(path, encoding='utf-8'):
    """
    加载 CSV 文件为字典列表
    """
    # 尝试使用 Path 对象读取
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # 处理可能的 BOM
    try:
        with open(path, newline='', encoding=encoding) as f:
            reader = csv.DictReader(f)
            return list(reader)
    except UnicodeDecodeError:
        # 如果 utf-8 失败，尝试 utf-8-sig
        if encoding == 'utf-8':
            with open(path, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                return list(reader)
        raise

def extract_booth_from_filename(filename):
    """Extract booth number from filename."""
    base = Path(filename).stem.strip()
    if not base:
        return None
    return base.split()[0]

