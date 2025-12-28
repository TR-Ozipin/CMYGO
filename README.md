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

### 🌐 浏览器脚本
- **X (Twitter) 品书快速保存工具**: 在 X 页面自动识别品书推文，一键下载图片

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

**数据提取机制**:
- 脚本会优先从页面底部的 JSON 数据中提取（最准确）
- 自动提取社团名、作者、摊位号、Twitter 链接、Pixiv 链接等
- 如果 JSON 提取失败，会回退到 DOM 解析

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

#### 🌐 步骤 0: 安装浏览器脚本（可选但推荐）

为了更方便地保存品书图片，建议先安装油猴脚本：

1. **安装 Tampermonkey 扩展**:
   - [Chrome 版本](https://chrome.google.com/webstore/detail/tampermonkey/)
   - [Firefox 版本](https://addons.mozilla.org/en-US/firefox/addon/tampermonkey/)
   - [Edge 版本](https://microsoftedge.microsoft.com/addons/detail/tampermonkey/)

2. **安装 CMYGO 品书保存脚本**:
   - 打开 `浏览器脚本/X (Twitter) 品书快速保存工具-1.0.0.user.js`
   - 点击 Tampermonkey 图标 → "Create a new script"
   - 粘贴脚本内容并保存

3. **使用方法**:
   - 访问 X (Twitter)，浏览任何用户主页
   - 包含"お品書き"、"Menu"等关键词的推文会被**自动高亮**
   - 推文下方会出现 **"💾 保存品书"** 按钮
   - 点击按钮，自动下载该推文的所有图片到 Downloads 文件夹
   - 文件名格式：`twitter-{username}-{tweetId}-{index}-{date}.jpg`（符合重命名脚本的格式）

4. **配置浏览器下载路径**（可选）:
   - Chrome: 设置 → 下载内容 → 位置 → 选择 `CMYGO/data/shinagaki/`
   - 这样下载的图片会直接进入待处理目录

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
│   └── catalog_sync.py     # Circle.ms 同步模块
├── data/                   # 数据目录
│   ├── 插画师数据库 - 主表.csv
│   ├── comike_info/        # 存放 Comike_Info CSV
│   └── shinagaki/          # 品书图片目录
├── output/                 # 输出目录（HTML 报告）
├── browser_data/           # 浏览器登录状态（自动生成）
└── 浏览器脚本/             # 原有的油猴脚本（备用）
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
**A**: 
1. 首先检查是否登录成功（浏览器窗口应该显示您的收藏列表）
2. 查看控制台输出，脚本会尝试从 JSON 提取，如果失败会提示错误信息
3. 使用调试模式检查页面结构：
```bash
uv run python main.py sync-debug
```

### Q2: 浏览器一直显示"正在被自动化程序控制"？
**A**: 这是正常现象。Playwright 会显示此提示，但不影响功能。我们已经设置了反检测参数。

### Q3: 登录状态丢失？
**A**: 删除 `browser_data/` 文件夹，重新运行 `sync` 命令并手动登录。

### Q4: 如何更新到 C108？
**A**: 修改 `config.yaml` 中的 `event_name: "C108"` 即可。无需修改代码。

### Q5: 分页功能正常吗？
**A**: 脚本会自动检测分页并遍历所有页面。如果您的收藏超过20个（默认每页显示数量），脚本会自动翻页。最多支持100页（2000个收藏）。

### Q6: 提取的数据包含哪些信息？
**A**: 
- **摊位**: 如 "水 西あ52ab"
- **社团**: 社团名称
- **作者**: 作者笔名
- **备注**: Twitter 和 Pixiv 链接（空格分隔）
- **社团详情**: Circle.ms 上的详情页链接
- **颜色**: 您在收藏时标记的颜色（如 color-1, color-2 等）

## 技术细节

### Circle.ms 数据提取原理

脚本采用**两层提取机制**：

1. **优先方案（JSON 提取）**:
   - Circle.ms 的收藏页面在底部内嵌了完整的 JSON 数据（`<script id="TheModel">`）
   - 包含所有社团的详细信息：名称、作者、摊位、外部链接等
   - 这是最稳定和准确的数据源

2. **回退方案（DOM 解析）**:
   - 如果 JSON 提取失败，会解析页面 HTML
   - 使用 CSS 选择器定位社团信息表格（`table.md-infotable`）
   - 提取每行的摊位、社团名、类型等信息

### 反爬虫策略

- 使用真实的 Chrome 浏览器（而非 Headless Chromium）
- 复用用户的登录会话（保存在 `browser_data/`）
- 添加随机延时（翻页时等待2秒）
- 设置反自动化检测参数（`--disable-blink-features=AutomationControlled`）

## 进阶使用

### 定时自动同步

您可以使用 cron (macOS/Linux) 或任务计划程序 (Windows) 设置定时任务：

**macOS/Linux cron 示例**:
```bash
# 每天凌晨 2 点自动同步并生成报告
0 2 * * * cd /path/to/CMYGO && /usr/local/bin/uv run python main.py auto
```

### 自定义选择器

如果 Circle.ms 改版导致 JSON 提取失效，您可以修改 `src/catalog_sync.py` 中的回退逻辑。

在 `extract_favorites_from_page` 函数的"方法2"部分，调整以下 CSS 选择器：
```python
circle_rows = page.query_selector_all('tr.webcatalog-circle-list-detail')  # 主行选择器
space_elem = row.query_selector('td.infotable-space span')  # 摊位
circle_name_elem = row.query_selector('td.infotable-circlename a')  # 社团名
```

## 贡献指南

欢迎提交 Issue 和 Pull Request！

**分支说明**:
- `main`: 稳定版本
- `Ozipin-mod107`: 当前开发分支（C107 版本重构）

**提交前请确保**:
- 代码通过 lint 检查
- 更新相关文档
- 测试核心功能正常运行

## 许可证

请查看 `LICENSE` 文件。

## 致谢

- 原作者: Ozipin (Saline/jin)
- 重构版本: Mod by Community
- 浏览器脚本: 见 `浏览器脚本/` 目录
- 数据来源: [Comike Web Catalog](https://webcatalog.circle.ms/)

---

**祝您 C107 顺利！品书收集愉快！🎉**
