# CMYGO - Comike 品书自动化管理工具

一个用于自动化整理同人展（Comiket）品书（Shinagaki/Menu）的 Python 工具集。

## 功能特性

### 🤖 自动化功能
- **Circle.ms 收藏同步**: 自动抓取 Web Catalog 上的收藏社团列表，无需手动导出 CSV
- **智能重命名**: 根据数据库自动将品书文件重命名为 `摊位号 社团名.jpg` 格式
- **进度监控**: 对比已有品书和收藏列表，生成待收集清单（HTML 报告）

### 📊 数据管理
- 支持插画师数据库匹配（社团名、Twitter ID 等）
- 支持 CSV 导入导出
- 自动备份原始文件

## 快速开始

### 环境要求
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (Python 包管理器)
- Google Chrome 浏览器（用于 Circle.ms 同步功能）

### 安装步骤

1. **克隆项目**
```bash
git clone <your-repo-url>
cd CMYGO
git checkout Ozipin-mod107
```

2. **安装依赖**
```bash
uv sync
```

3. **配置文件**

复制环境变量模板：
```bash
cp .env.example .env
```

编辑 `config.yaml`，根据您的实际路径调整：
```yaml
event_name: "C107"

paths:
  database: "data/插画师数据库 - 主表.csv"
  comike_info_dir: "data/comike_info"
  shinagaki_dir: "data/shinagaki"
  output_dir: "output"
```

4. **准备数据目录**
```bash
mkdir -p data/comike_info data/shinagaki output
```

将您的插画师数据库 CSV 放入 `data/` 目录。

## 使用指南

### 命令概览

```bash
# 查看帮助
uv run python main.py --help

# 1. 同步 Circle.ms 收藏（自动登录并抓取）
uv run python main.py sync

# 2. 重命名本地品书文件
uv run python main.py rename

# 3. 生成进度监控报告
uv run python main.py monitor

# 4. 全自动模式（依次执行上述三步）
uv run python main.py auto

# 调试模式（检查页面结构）
uv run python main.py sync-debug
```

### 详细使用流程

#### 📥 步骤 1: 同步 Circle.ms 收藏

首次运行会自动打开 Chrome 浏览器窗口：

```bash
uv run python main.py sync
```

**操作说明**:
1. 如果未登录，浏览器会跳转到登录页面
2. **手动登录** Circle.ms 账号（建议勾选"保持登录"）
3. 登录成功后，脚本会自动继续执行
4. 脚本将遍历您的所有收藏，并导出为 `data/comike_info/Comike_Info_YYYY-MM-DD_HH-MM-SS.csv`

**后续运行**:
- 因为登录状态已保存在 `browser_data/` 文件夹中，后续运行会自动跳过登录步骤

#### 🏷️ 步骤 2: 自动重命名品书

将下载的品书图片（文件名格式如 `twitter-XXX-123-2024.12.28.jpg`）放入 `data/shinagaki/` 目录，然后运行：

```bash
uv run python main.py rename
```

**处理逻辑**:
1. 从文件名提取 Twitter ID
2. 在数据库中匹配社团信息
3. 将文件复制到 `data/shinagaki/已处理/` 并重命名为 `摊位号 标识符.jpg`
4. 原文件移动到 `data/shinagaki/原名备份/`

#### 📊 步骤 3: 生成进度报告

```bash
uv run python main.py monitor
```

**输出结果**:
- 在 `output/` 目录生成 HTML 文件（按颜色分组）
- 列出"已收藏但暂无品书"的社团
- 包含社团详情链接和数据库链接（Twitter）

打开 HTML 文件，点击链接即可快速跳转到对应社团的 X 主页。

## 项目结构

```
CMYGO/
├── main.py                 # 统一入口
├── config.yaml             # 配置文件
├── .env                    # 环境变量（账号密码，不提交到 Git）
├── pyproject.toml          # uv 依赖管理
├── README.md               # 本文档
├── src/                    # 源代码
│   ├── utils.py            # 配置加载、路径处理
│   ├── core.py             # 核心逻辑（CSV 读取、文件名解析）
│   ├── rename.py           # 重命名模块
│   ├── report.py           # HTML 报告生成
│   └── catalog_sync.py     # Circle.ms 同步模块 (NEW)
├── data/                   # 数据目录
│   ├── 插画师数据库 - 主表.csv
│   ├── comike_info/        # 存放 Comike_Info CSV
│   └── shinagaki/          # 品书图片目录
├── output/                 # 输出目录（HTML 报告）
└── browser_data/           # 浏览器登录状态（自动生成）
```

## 配置说明

### config.yaml

```yaml
event_name: "C107"  # 当前活动名称

paths:
  database: "data/插画师数据库 - 主表.csv"  # 数据库文件路径
  comike_info_dir: "data/comike_info"      # Comike Info CSV 目录
  shinagaki_dir: "data/shinagaki"          # 品书图片目录
  output_dir: "output"                     # HTML 输出目录
  backup_subdir_name: "原名备份"           # 备份子目录名
  processed_subdir_name: "已处理"         # 已处理子目录名

filters:
  target_colors: []  # 筛选特定颜色，留空表示全部

patterns:
  twitter_id: "twitter-([^-]+)-\\d+-\\d+"  # Twitter ID 提取正则
```

### .env (可选)

如果您不想使用浏览器手动登录，可以配置自动登录（**不推荐，有安全风险**）：

```env
CIRCLE_MS_EMAIL=your_email@example.com
CIRCLE_MS_PASSWORD=your_password
```

## 常见问题

### Q1: `sync` 命令无法提取数据？
**A**: Circle.ms 的页面结构可能变更。请使用调试模式检查：
```bash
uv run python main.py sync-debug
```
在打开的浏览器中，使用开发者工具（F12）查看收藏列表的 HTML 结构，然后更新 `src/catalog_sync.py` 中的选择器。

### Q2: 浏览器一直显示"正在被自动化程序控制"？
**A**: 这是正常现象。Playwright 会显示此提示，但不影响功能。

### Q3: 登录状态丢失？
**A**: 删除 `browser_data/` 文件夹，重新运行 `sync` 命令并手动登录。

### Q4: 如何更新到 C108？
**A**: 修改 `config.yaml` 中的 `event_name: "C108"` 即可。

## 进阶使用

### 定时自动同步

您可以使用 cron (macOS/Linux) 或任务计划程序 (Windows) 设置定时任务：

**macOS/Linux cron 示例**:
```bash
# 每天凌晨 2 点自动同步并生成报告
0 2 * * * cd /path/to/CMYGO && /usr/local/bin/uv run python main.py auto
```

### 自定义选择器

如果 Circle.ms 改版，您需要修改 `src/catalog_sync.py` 中的 CSS 选择器。

在 `extract_favorites_from_page` 函数中，调整以下部分：
```python
circle_cards = page.query_selector_all('.exhibitorDataRow')  # 修改为实际的类名
```

## 贡献指南

欢迎提交 Issue 和 Pull Request！

**分支说明**:
- `main`: 稳定版本
- `Ozipin-mod107`: 当前开发分支（C107 版本重构）

## 许可证

请查看 `LICENSE` 文件。

## 致谢

- 原作者: Ozipin (Saline/jin)
- 重构版本: Mod by Community
- 浏览器脚本: 见 `浏览器脚本/` 目录

---

**祝您 C107 顺利！品书收集愉快！🎉**

