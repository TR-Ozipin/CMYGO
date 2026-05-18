# CMYGO - Comike 品书自动化管理工具

一个用于自动化整理同人展（Comiket）品书（Shinagaki/Menu）的 Python 工具集。

## 功能特性

### Automation
- **Circle.ms Favorites Sync**: Automatically scrape saved circles from Web Catalog, no manual CSV export needed
- **Smart Rename**: Auto-rename shinagaki files to `booth_number circle_name.jpg` format using database lookup
- **Progress Monitoring**: Compare existing shinagaki files against favorites list and generate pending collection report (HTML)

### Data Management
- SQLite database for illustrator/circle information (circle name, Twitter ID, etc.)
- CSV import/export support
- Automatic original file backup

### Browser Scripts
- **X (Twitter) Shinagaki Quick Save**: Auto-detect shinagaki tweets on X and download images with one click

## Quick Start

### Requirements
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Google Chrome browser (required for Circle.ms sync)

### Installation

1. **Clone the project**
```bash
git clone <your-repo-url>
cd CMYGO
git checkout Ozipin-mod107
```

2. **Install dependencies**
```bash
uv sync
```

3. **Install Playwright browsers**
```bash
uv run playwright install chromium
```

4. **Configure**

Copy environment template:
```bash
cp .env.example .env
```

Edit `config.yaml` with your paths:
```yaml
event_name: "C107"

paths:
  database: "data/database.db"
  csv_database: "data/illustrator_database_master.csv"
  comike_info_dir: "data/comike_info"
  shinagaki_dir: "data/shinagaki"
  output_dir: "output"
```

5. **Prepare data directories**
```bash
mkdir -p data/comike_info data/shinagaki output
```

Place your illustrator database CSV file in the `data/` directory.

6. **Migrate CSV to SQLite** (required first step)
```bash
uv run python main.py migrate
```

This imports your CSV database into SQLite for faster lookups.

## Usage Guide

### Command Overview

```bash
# Show help
uv run python main.py --help

# Migrate CSV database to SQLite (run once)
uv run python main.py migrate

# Sync Circle.ms favorites (auto-login and scrape)
uv run python main.py sync

# Rename local shinagaki files
uv run python main.py rename

# Generate progress monitoring report
uv run python main.py monitor

# Full auto mode (sync -> rename -> monitor)
uv run python main.py auto

# Debug mode (inspect page structure)
uv run python main.py sync-debug
```

### Detailed Workflow

#### Step 1: Migrate Database (First Time Only)

Before using any features, migrate your CSV database to SQLite:

```bash
uv run python main.py migrate
```

This will:
- Read `data/illustrator_database_master.csv`
- Create `data/database.db` (SQLite)
- Import all circle/illustrator data
- Also import existing Comike Info CSVs if available

#### Step 2: Sync Circle.ms Favorites

First run will open a Chrome browser window:

```bash
uv run python main.py sync
```

**Instructions**:
1. If not logged in, browser will redirect to login page
2. **Manually log in** to your Circle.ms account (check "keep me logged in")
3. After login, script continues automatically
4. Script iterates all your favorites and saves to:
   - `data/comike_info/Comike_Info_YYYY-MM-DD_HH-MM-SS.csv`
   - `data/database.db` (comike_info table)

**Data Extraction**:
- Prioritizes embedded JSON data on the page (most accurate)
- Extracts: circle name, author, booth number, Twitter link, Pixiv link, etc.
- Falls back to DOM parsing if JSON extraction fails

**Subsequent Runs**:
- Login state is saved in `browser_data/`, so login is skipped

#### Step 3: Auto Rename Shinagaki Files

Place downloaded shinagaki images (filename format like `twitter-XXX-123-2024.12.28.jpg`) into `data/shinagaki/`, then run:

```bash
uv run python main.py rename
```

**Processing Logic**:
1. Extract Twitter ID from filename
2. Look up circle info in SQLite database
3. Copy file to `data/shinagaki/processed/` renamed as `booth_number identifier.jpg`
4. Move original file to `data/shinagaki/backup/`

#### Step 4: Generate Progress Report

```bash
uv run python main.py monitor
```

**Output**:
- Generates HTML files in `output/` directory (grouped by color)
- Lists circles that are "favorited but missing shinagaki"
- Includes circle detail links and database links (Twitter)

Open the HTML file and click links to jump to the circle's X profile.

#### Optional: Install Browser Script (Recommended)

For easier shinagaki image saving, install the Tampermonkey script:

1. **Install Tampermonkey extension**:
   - [Chrome](https://chrome.google.com/webstore/detail/tampermonkey/)
   - [Firefox](https://addons.mozilla.org/en-US/firefox/addon/tampermonkey/)
   - [Edge](https://microsoftedge.microsoft.com/addons/detail/tampermonkey/)

2. **Install CMYGO Shinagaki Save Script**:
   - Open `browser_scripts/X (Twitter) Shinagaki Quick Save Tool-1.0.0.user.js`
   - Click Tampermonkey icon -> "Create a new script"
   - Paste script content and save

3. **Usage**:
   - Visit X (Twitter) and browse any user profile
   - Tweets containing "お品書き", "Menu", etc. are **auto-highlighted**
   - A **"Save Shinagaki"** button appears below the tweet
   - Click to auto-download all images from that tweet
   - Filename format: `twitter-{username}-{tweetId}-{index}-{date}.jpg`

4. **Configure Browser Download Path** (optional):
   - Chrome: Settings -> Downloads -> Location -> Select `CMYGO/data/shinagaki/`
   - Downloaded images go directly into the processing directory

## Project Structure

```
CMYGO/
├── main.py                 # Entry point
├── config.yaml             # Configuration file
├── .env                    # Environment variables (not committed to Git)
├── pyproject.toml          # uv dependency management
├── README.md               # This file
├── src/                    # Source code
│   ├── utils.py            # Config loading, path handling
│   ├── core.py             # Core logic (filename parsing)
│   ├── database.py         # SQLite database module (new)
│   ├── rename.py           # Rename module
│   ├── report.py           # HTML report generation
│   └── catalog_sync.py     # Circle.ms sync module
├── data/                   # Data directory
│   ├── database.db         # SQLite database (generated)
│   ├── illustrator_database_master.csv  # Original CSV (for migration)
│   ├── comike_info/        # Comike Info CSV files
│   └── shinagaki/          # Shinagaki images
│       ├── processed/      # Renamed files
│       └── backup/         # Original file backups
├── output/                 # Output directory (HTML reports)
├── browser_data/           # Browser login state (auto-generated)
└── browser_scripts/        # Tampermonkey user scripts
```

## Configuration

### config.yaml

```yaml
event_name: "C107"        # Current event name

paths:
  database: "data/database.db"           # SQLite database path
  csv_database: "data/illustrator_database_master.csv"  # CSV for migration
  comike_info_dir: "data/comike_info"   # Comike Info CSV directory
  shinagaki_dir: "data/shinagaki"       # Shinagaki images directory
  output_dir: "output"                   # HTML output directory
  backup_subdir_name: "backup"          # Backup subdirectory name
  processed_subdir_name: "processed"     # Processed subdirectory name

filters:
  target_colors: []   # Filter specific colors, empty = all colors

patterns:
  twitter_id: "twitter-([^-]+)-\\d+-\\d+"  # Twitter ID extraction regex
```

### .env (Optional)

If you prefer auto-login over manual browser login (**not recommended, security risk**):

```env
CIRCLE_MS_EMAIL=your_email@example.com
CIRCLE_MS_PASSWORD=your_password
```

## Database Schema

### circles Table (Illustrator Database)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | TEXT | Circle name (default) |
| name_alt | TEXT | Alternative circle name |
| twitter_id | TEXT | Twitter ID (primary) |
| twitter_id_alt | TEXT | Twitter ID (alternative) |
| twitter_url | TEXT | Twitter profile URL |
| pixiv_url | TEXT | Pixiv profile URL |
| identifier | TEXT | Circle identifier/tag |
| author | TEXT | Author pen name |

**Indexes**: `twitter_id`, `twitter_id_alt`, `name`

### comike_info Table (Favorites Data)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| event_name | TEXT | Event name (e.g., "C107") |
| booth | TEXT | Booth number/location |
| circle_name | TEXT | Circle name |
| author | TEXT | Author name |
| notes | TEXT | Notes (Twitter/Pixiv links) |
| merged | TEXT | Combined booth + circle name |
| detail_url | TEXT | Circle.ms detail page URL |
| color | TEXT | Favorite color tag |
| imported_at | TIMESTAMP | Import timestamp |

**Indexes**: `event_name`, `circle_name`, `booth`

## FAQ

### Q1: `sync` command fails to extract data?
**A**:
1. Check if login succeeded (browser should show your favorites list)
2. Check console output - script tries JSON extraction first, then DOM parsing
3. Use debug mode to inspect page structure:
```bash
uv run python main.py sync-debug
```

### Q2: Browser shows "being controlled by automated software"?
**A**: This is normal. Playwright shows this notice but it does not affect functionality. Anti-detection parameters are configured.

### Q3: Login state lost?
**A**: Delete `browser_data/` folder and run `sync` again to manually log in.

### Q4: How to update to C108?
**A**: Change `event_name: "C108"` in `config.yaml`. No code changes needed.

### Q5: Does pagination work?
**A**: Script auto-detects pagination and iterates all pages. If you have more than 20 favorites (default per page), it auto-flips. Supports up to 100 pages (2000 favorites).

### Q6: What data is extracted?
**A**:
- **Booth**: e.g., "水 西あ52ab"
- **Circle**: Circle name
- **Author**: Author pen name
- **Notes**: Twitter and Pixiv links (space-separated)
- **Detail URL**: Circle.ms detail page link
- **Color**: Color tag you assigned when favoriting (color-1, color-2, etc.)

## Technical Details

### Circle.ms Data Extraction

Two-layer extraction mechanism:

1. **Primary (JSON Extraction)**:
   - Circle.ms favorites page embeds full JSON data (`<script id="TheModel">`)
   - Contains all circle details: name, author, booth, external links
   - Most stable and accurate data source

2. **Fallback (DOM Parsing)**:
   - If JSON extraction fails, parses page HTML
   - Uses CSS selectors to locate circle info tables
   - Extracts booth, circle name, genre per row

### Anti-Scraping Measures

- Uses real Chrome browser (not headless Chromium)
- Reuses user login session (saved in `browser_data/`)
- Adds random delays (2 seconds between page flips)
- Sets anti-automation flags (`--disable-blink-features=AutomationControlled`)

## Advanced Usage

### Scheduled Auto-Sync

Use cron (macOS/Linux) or Task Scheduler (Windows) for automated runs:

**macOS/Linux cron example**:
```bash
# Sync and generate report daily at 2 AM
0 2 * * * cd /path/to/CMYGO && /usr/local/bin/uv run python main.py auto
```

### Custom Selectors

If Circle.ms redesign breaks JSON extraction, modify fallback logic in `src/catalog_sync.py`:

In `extract_favorites_from_page` function (Method 2), adjust CSS selectors:
```python
circle_rows = page.query_selector_all('tr.webcatalog-circle-list-detail')
space_elem = row.query_selector('td.infotable-space span')
circle_name_elem = row.query_selector('td.infotable-circlename a')
```

## Contributing

Issues and Pull Requests welcome!

**Branches**:
- `main`: Stable release
- `Ozipin-mod107`: Active development (C107 refactor)

**Before submitting**:
- Code passes lint checks (`uv run ruff check .`)
- Documentation is updated
- Core features are tested

## License

See `LICENSE` file.

## Credits

- Original author: Ozipin (Saline/jin)
- Refactored version: Community mod
- Browser scripts: See `browser_scripts/` directory
- Data source: [Comike Web Catalog](https://webcatalog.circle.ms/)

---

**Good luck with C107! Happy shinagaki collecting!**
