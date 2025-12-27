import yaml
from pathlib import Path

def load_config(config_path="config.yaml"):
    """
    加载配置文件
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件未找到: {config_path}")
    
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config

def get_path(config, key, base_dir=None):
    """
    获取配置中的路径，并转换为 Path 对象
    支持相对路径（相对于 base_dir 或当前工作目录）
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    raw_path = config
    for k in key.split('.'):
        raw_path = raw_path.get(k)
        if raw_path is None:
            return None
            
    p = Path(raw_path)
    if not p.is_absolute():
        p = base_dir / p
    
    return p

