# CMYGO - Product Requirements Document

## 1. Overview

### 1.1 Purpose
CMYGO is an automation tool for managing **shinagaki** (品書/menu) from Comike doujinshi exhibitions. It syncs circle favorites from Circle.ms, renames shinagaki images using database lookups, and generates progress reports.

### 1.2 Target Users
- Comike attendees who collect shinagaki from multiple circles
- Users who want to organize downloaded shinagaki images automatically
- Users who track collection progress against their Circle.ms favorites

### 1.3 Problem Statement
Currently, collecting and organizing shinagaki requires:
- Manual downloading from X (Twitter) or other sources
- Manual file renaming using circle names and booth numbers
- Manual tracking of which circles still need shinagaki collected
- No centralized storage or cloud access to collected shinagaki

### 1.4 Solution
An automated pipeline that:
1. Scrapes Circle.ms favorites into a structured database
2. Matches downloaded shinagaki images to circles via Twitter ID
3. Renames and organizes files automatically
4. Generates reports on collection progress
5. (Future) Runs as a cloud service with object storage

---

## 2. Current Architecture (v1.0)

### 2.1 Tech Stack
| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| Package Manager | uv |
| Database | SQLite |
| Browser Automation | Playwright + Chrome |
| Config | YAML |
| Linting | Ruff |

### 2.2 Data Flow
```
[Circle.ms] → (Playwright scrape) → [SQLite: comike_info]
[CSV Import] → (migrate command) → [SQLite: circles]
[Local Images] → (Twitter ID match) → [Renamed Files]
[SQLite + Files] → (compare) → [HTML Reports]
```

### 2.3 Database Schema

**circles** (Illustrator Database)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| name | TEXT | Circle name (default) |
| name_alt | TEXT | Alternative circle name |
| twitter_id | TEXT UNIQUE | Twitter handle (primary) |
| twitter_id_alt | TEXT | Twitter handle (alternative) |
| twitter_url | TEXT | Full Twitter profile URL |
| pixiv_url | TEXT | Pixiv profile URL |
| identifier | TEXT | Circle identifier/tag |
| author | TEXT | Author pen name |

**comike_info** (Favorites Data)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| event_name | TEXT | Event code (e.g., "C107") |
| booth | TEXT | Booth location |
| circle_name | TEXT | Circle name |
| author | TEXT | Author name |
| notes | TEXT | External links (Twitter/Pixiv) |
| merged | TEXT | booth + circle_name combined |
| detail_url | TEXT | Circle.ms detail page URL |
| color | TEXT | Favorite color tag |
| imported_at | TIMESTAMP | Import timestamp |

### 2.4 Commands
| Command | Description |
|---------|-------------|
| `migrate` | Import CSV database into SQLite |
| `sync` | Scrape Circle.ms favorites, save to SQLite + CSV |
| `rename` | Match and rename shinagaki images |
| `monitor` | Generate HTML progress reports |
| `auto` | Run sync → rename → monitor sequentially |
| `sync-debug` | Open browser for debugging page structure |

---

## 3. Target Architecture (v2.0)

### 3.1 Goals
1. **Cloud Deployment**: Run as a Docker container service
2. **Object Storage**: Use Cloudflare R2 for file storage (images, CSV, reports)
3. **API Access**: Provide REST API for all operations
4. **Headless Operation**: No local browser required
5. **Remote Login**: Support Circle.ms authentication without local Chrome

### 3.2 Target Tech Stack
| Component | Technology |
|-----------|------------|
| Runtime | Docker Container |
| API Framework | FastAPI |
| Database | SQLite (container) or PostgreSQL (external) |
| Object Storage | Cloudflare R2 (S3-compatible) |
| Browser Automation | Playwright headless + Chromium in container |
| Task Queue | (Optional) Redis + Celery for async jobs |
| Config | YAML + Environment Variables |

### 3.3 Target Data Flow
```
[Circle.ms] → (Playwright headless) → [R2: comike_info/] + [SQLite: comike_info]
[CSV Import] → (API call) → [SQLite: circles]
[R2: shinagaki/] → (Twitter ID match) → [R2: shinagaki/processed/]
[SQLite + R2] → (compare) → [R2: reports/]
[Shinagaki Image] → (Vision LLM Runner) → (extract booth/circle) → [SQLite match] → [R2: processed/]
```

### 3.5 Vision Recognition Service

**Purpose**: Extract structured information (booth, circle name, author) from shinagaki images when filename-based matching fails.

**Architecture**:
```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Shinagaki    │────>│  LLM Runner      │────>│   SQLite     │
│  Image (R2)   │     │  (FastAPI)       │     │  (match)     │
└──────────────┘     └─────────────────┘     └──────────────┘
                              │
                       ┌─────────────────┐
                       │  Vision Model    │
                       │  Qwen-VL /       │
                       │  GPT-4o API /    │
                       │  Ollama (local)  │
                       └─────────────────┘
```

**Fallback Chain for Rename**:
1. Extract Twitter ID from filename (current method)
2. If fails → call Vision LLM Runner to recognize image content
3. Use recognized `circle_name` or `twitter_id` to query SQLite
4. If still fails → mark as `unrecognized` for manual review

**Output Schema**:
```json
{
  "booth": "水 西あ52ab",
  "circle_name": "社团名",
  "author": "作者名",
  "event": "ComiC107",
  "twitter_id": "username",
  "confidence": 0.92,
  "raw_text": "识别到的全部文字"
}
```

### 3.4 R2 Bucket Structure
```
cmygo-data/
├── shinagaki/
│   └── {event}/
│       ├── raw/              # Original downloaded images
│       ├── processed/        # Renamed images
│       └── backup/           # Original file backups
├── comike_info/
│   └── {event}/
│       └── Comike_Info_{timestamp}.csv
├── reports/
│   └── {event}/
│       └── {color}.html
└── browser_data/             # Optional: serialized cookies
    └── {user_id}/
```

---

## 4. Functional Requirements

### 4.1 Database Management (FR-01)

**Priority**: P0 (Current)

| ID | Requirement | Status |
|----|-------------|--------|
| FR-01.1 | Support CSV import to SQLite via `migrate` command | ✅ Done |
| FR-01.2 | Query circles by Twitter ID (primary or alt) | ✅ Done |
| FR-01.3 | Query comike_info by event_name | ✅ Done |
| FR-01.4 | Build circle_name → booth mapping per event | ✅ Done |
| FR-01.5 | Support multiple events in same database | ✅ Done |

### 4.2 Circle.ms Sync (FR-02)

**Priority**: P0 (Current)

| ID | Requirement | Status |
|----|-------------|--------|
| FR-02.1 | Launch browser and navigate to favorites page | ✅ Done |
| FR-02.2 | Detect login state and wait for manual login | ✅ Done |
| FR-02.3 | Extract data from embedded JSON (primary method) | ✅ Done |
| FR-02.4 | Fallback to DOM parsing if JSON fails | ✅ Done |
| FR-02.5 | Handle pagination (up to 100 pages) | ✅ Done |
| FR-02.6 | Save results to both CSV and SQLite | ✅ Done |
| FR-02.7 | Persist browser session for subsequent runs | ✅ Done |
| FR-02.8 | Support multi-language pagination detection | ✅ Done |

### 4.3 Shinagaki Rename (FR-03)

**Priority**: P0 (Current)

| ID | Requirement | Status |
|----|-------------|--------|
| FR-03.1 | Extract Twitter ID from filename via regex | ✅ Done |
| FR-03.2 | Look up circle by Twitter ID in database | ✅ Done |
| FR-03.3 | Get booth number from comike_info | ✅ Done |
| FR-03.4 | Rename file to `{booth} {identifier}.jpg` | ✅ Done |
| FR-03.5 | Handle multiple files per Twitter ID (add index) | ✅ Done |
| FR-03.6 | Fallback to notes-based matching if DB fails | ✅ Done |
| FR-03.7 | Replace illegal filename characters with fullwidth | ✅ Done |
| FR-03.8 | Backup original files to separate directory | ✅ Done |

### 4.4 Progress Monitoring (FR-04)

**Priority**: P0 (Current)

| ID | Requirement | Status |
|----|-------------|--------|
| FR-04.1 | Scan local directory for existing booth numbers | ✅ Done |
| FR-04.2 | Query comike_info for event | ✅ Done |
| FR-04.3 | Filter out circles that already have shinagaki | ✅ Done |
| FR-04.4 | Enrich results with Twitter links from circles table | ✅ Done |
| FR-04.5 | Group remaining circles by color tag | ✅ Done |
| FR-04.6 | Generate HTML report per color group | ✅ Done |
| FR-04.7 | Include "View Detail" button linking to Circle.ms | ✅ Done |
| FR-04.8 | Auto-linkify URLs in notes column | ✅ Done |

### 4.5 API Service (FR-05)

**Priority**: P1 (v2.0)

| ID | Requirement | Status |
|----|-------------|--------|
| FR-05.1 | REST API for all operations | ❌ Todo |
| FR-05.2 | `POST /api/sync` - trigger favorites sync | ❌ Todo |
| FR-05.3 | `GET /api/sync/status` - query sync progress | ❌ Todo |
| FR-05.4 | `POST /api/rename` - trigger rename job | ❌ Todo |
| FR-05.5 | `GET /api/rename/status` - query rename progress | ❌ Todo |
| FR-05.6 | `GET /api/monitor` - generate and return report | ❌ Todo |
| FR-05.7 | `GET /api/circles` - list/search circles | ❌ Todo |
| FR-05.8 | `GET /api/shinagaki` - list uploaded shinagaki | ❌ Todo |
| FR-05.9 | `POST /api/migrate` - trigger CSV migration | ❌ Todo |
| FR-05.10 | `GET /api/health` - health check endpoint | ❌ Todo |

### 4.6 R2 Storage Integration (FR-06)

**Priority**: P1 (v2.0)

| ID | Requirement | Status |
|----|-------------|--------|
| FR-06.1 | Configure R2 via environment variables | ❌ Todo |
| FR-06.2 | Upload/download files to/from R2 | ❌ Todo |
| FR-06.3 | Store shinagaki images in R2 | ❌ Todo |
| FR-06.4 | Store Comike Info CSV in R2 | ❌ Todo |
| FR-06.5 | Store HTML reports in R2 | ❌ Todo |
| FR-06.6 | Generate presigned URLs for private files | ❌ Todo |
| FR-06.7 | List files in R2 by event/prefix | ❌ Todo |
| FR-06.8 | Delete files from R2 | ❌ Todo |

### 4.7 Docker Deployment (FR-07)

**Priority**: P1 (v2.0)

| ID | Requirement | Status |
|----|-------------|--------|
| FR-07.1 | Dockerfile with Python + Chromium | ❌ Todo |
| FR-07.2 | docker-compose.yml for local development | ❌ Todo |
| FR-07.3 | Volume mount for browser_data persistence | ❌ Todo |
| FR-07.4 | Volume mount for SQLite database | ❌ Todo |
| FR-07.5 | Health check in Docker config | ❌ Todo |
| FR-07.6 | .dockerignore for clean builds | ❌ Todo |
| FR-07.7 | Multi-stage build for smaller image | ❌ Todo |

### 4.8 Headless Browser & Remote Login (FR-08)

**Priority**: P1 (v2.0)

| ID | Requirement | Status |
|----|-------------|--------|
| FR-08.1 | Run Playwright in headless mode | ❌ Todo |
| FR-08.2 | Option A: noVNC for remote manual login | ❌ Todo |
| FR-08.3 | Option B: Cookie import from JSON file | ❌ Todo |
| FR-08.4 | Persist cookies to volume between restarts | ❌ Todo |
| FR-08.5 | Detect expired session and prompt re-login | ❌ Todo |

### 4.9 Task Queue & Async Jobs (FR-09)

**Priority**: P2 (v2.1)

| ID | Requirement | Status |
|----|-------------|--------|
| FR-09.1 | Run sync/rename as background tasks | ❌ Todo |
| FR-09.2 | Track task status (pending/running/completed/failed) | ❌ Todo |
| FR-09.3 | Return task ID from POST endpoints | ❌ Todo |
| FR-09.4 | Poll task status via GET /api/*/status | ❌ Todo |
| FR-09.5 | Optional: Redis as task broker | ❌ Todo |
| FR-09.6 | Task result storage and cleanup | ❌ Todo |

### 4.10 Web Dashboard (FR-10)

**Priority**: P3 (v2.2)

| ID | Requirement | Status |
|----|-------------|--------|
| FR-10.1 | Simple frontend (Streamlit or vanilla HTML/JS) | ❌ Todo |
| FR-10.2 | Dashboard showing collection progress | ❌ Todo |
| FR-10.3 | Trigger sync/rename/monitor from UI | ❌ Todo |
| FR-10.4 | Browse and download shinagaki images | ❌ Todo |
| FR-10.5 | Search circles by name or Twitter ID | ❌ Todo |
| FR-10.6 | View pending collection list | ❌ Todo |

### 4.11 Shinagaki Vision Recognition (FR-11)

**Priority**: P2 (v2.1)

Extract structured information from shinagaki images using Vision LLM. Used as fallback when filename-based matching fails.

| ID | Requirement | Status |
|----|-------------|--------|
| FR-11.1 | FastAPI service for image recognition | ❌ Todo |
| FR-11.2 | Accept image via file upload or R2 presigned URL | ❌ Todo |
| FR-11.3 | Support cloud Vision API (GPT-4o, Claude Vision, Qwen-VL) | ❌ Todo |
| FR-11.4 | Support local Vision model via Ollama (Qwen2-VL, LLaVA) | ❌ Todo |
| FR-11.5 | Return structured JSON: booth, circle_name, author, event, twitter_id | ❌ Todo |
| FR-11.6 | Include confidence score per field | ❌ Todo |
| FR-11.7 | Cache recognition results by image hash (avoid re-processing) | ❌ Todo |
| FR-11.8 | Batch processing support (queue multiple images) | ❌ Todo |
| FR-11.9 | Integrate into rename flow as fallback when filename match fails | ❌ Todo |
| FR-11.10 | Mark low-confidence results for manual review | ❌ Todo |
| FR-11.11 | GPU support in Docker (NVIDIA Container Toolkit) | ❌ Todo |
| FR-11.12 | Configurable model provider via env vars | ❌ Todo |

**Model Provider Options**:

| Provider | Model | Cost | GPU Required | Japanese Accuracy |
|----------|-------|------|--------------|-------------------|
| OpenAI | GPT-4o | ~$0.01/image | No | High |
| Anthropic | Claude Sonnet | ~$0.008/image | No | High |
| Alibaba | Qwen-VL | ~$0.005/image | No | Very High (Chinese/Japanese optimized) |
| Local (Ollama) | Qwen2-VL-7B | Free | Yes (4GB VRAM) | Medium-High |
| Local (Ollama) | LLaVA-1.6-34B | Free | Yes (24GB VRAM) | Medium |
| PaddleOCR | PP-OCRv4 | Free | No (CPU OK) | High (text only, no understanding) |

**Recommended**: Qwen-VL API (cloud) for accuracy + cost balance; Qwen2-VL-7B (local) for privacy/bulk processing.

**Prompt Template**:
```
You are a shinagaki (品書) parser. Extract structured information from this Comike doujinshi menu image.

Return JSON only:
{
  "booth": "booth location (e.g., 水 西あ52ab)",
  "circle_name": "circle/doujin group name",
  "author": "author/illustrator name",
  "event": "event name (e.g., ComiC107)",
  "twitter_id": "twitter handle without @ (if visible)",
  "raw_text": "all recognized text in reading order"
}

Rules:
- Booth is usually at the top, largest text
- Circle name is the most prominent text (often with logo)
- Ignore menu item listings and small print
- If a field is not visible, return null
- Preserve original Japanese/Chinese characters, do not translate
```

---

## 5. Non-Functional Requirements

### 5.1 Performance
| Metric | Target |
|--------|--------|
| Sync 100 circles | < 5 minutes |
| Rename 1000 images | < 2 minutes |
| API response time | < 500ms (excluding sync/rename jobs) |
| Database query time | < 100ms |

### 5.2 Reliability
- Browser automation should retry on transient network errors (max 3 retries)
- File operations must be atomic (no partial uploads to R2)
- Database transactions for multi-row inserts

### 5.3 Security
- R2 credentials stored only in environment variables
- No secrets in Docker image or repository
- Presigned URLs expire within 1 hour
- Browser data (cookies) stored in private volume

### 5.4 Scalability
- Support multiple events simultaneously (C107, C108, etc.)
- R2 bucket structure allows per-event isolation
- Database schema supports unlimited circles and events

### 5.5 Maintainability
- All code passes `ruff check`
- Type hints on all public functions
- English comments and documentation
- Modular design: storage layer abstracted for testing

---

## 6. Development Phases

### Phase 1: API Service (Estimated: 3 days)
- Introduce FastAPI
- Wrap existing CLI commands as API endpoints
- Make Playwright headless configurable
- Write Dockerfile and docker-compose.yml
- Volume mounts for browser_data and database

**Deliverables**: `src/api/`, `Dockerfile`, `docker-compose.yml`

### Phase 2: R2 Storage (Estimated: 3 days)
- Add boto3 dependency
- Create `src/storage.py` with R2 client
- Migrate file I/O to R2 operations
- Add presigned URL generation
- Update config.yaml with R2 settings

**Deliverables**: `src/storage.py`, updated `catalog_sync.py`, `rename.py`, `report.py`

### Phase 3: Remote Login (Estimated: 2 days)
- Implement cookie import/export
- Optionally: add noVNC sidecar container
- Session expiration detection
- Cookie persistence to volume

**Deliverables**: `src/auth.py`, updated `catalog_sync.py`

### Phase 4: Async Tasks (Estimated: 3 days)
- Background task execution
- Task status tracking
- API endpoints for status polling
- Optional: Redis integration

**Deliverables**: `src/tasks.py`, `src/queue.py`, updated API

### Phase 5: Dashboard (Estimated: 3 days, optional)
- Streamlit or static frontend
- Progress visualization
- File browser
- Circle search

**Deliverables**: `frontend/` or `src/dashboard.py`

### Phase 6: Vision Recognition (Estimated: 5-7 days)
- Create `src/vision.py` with Vision LLM client abstraction
- Support multiple model providers (OpenAI, Anthropic, Qwen, Ollama)
- Implement recognition result caching (by image hash)
- Add `POST /api/recognize` endpoint
- Integrate vision fallback into rename flow
- Write `Dockerfile.vision` with GPU support (CUDA)
- Update docker-compose.yml with vision service
- Prompt engineering and accuracy testing with sample shinagaki images
- Confidence threshold configuration

**Deliverables**: `src/vision.py`, `Dockerfile.vision`, updated `rename.py`, `docker-compose.yml`

---

## 7. Environment Variables

```env
# Application
EVENT_NAME=C107
HEADLESS=true
API_HOST=0.0.0.0
API_PORT=8000

# R2 Storage
R2_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
R2_ACCESS_KEY=<access_key>
R2_SECRET_KEY=<secret_key>
R2_BUCKET=cmygo-data

# Database
DB_PATH=/data/database.db

# Browser
BROWSER_DATA_DIR=/data/browser_data

# Optional: Redis (Phase 4)
REDIS_URL=redis://redis:6379/0

# Vision Recognition (Phase 6)
VISION_PROVIDER=qwen_vl              # qwen_vl | gpt4o | claude | ollama
VISION_MODEL=Qwen-VL-Max             # Model name
VISION_API_KEY=<api_key>             # API key for cloud providers
VISION_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
VISION_CONFIDENCE_THRESHOLD=0.7      # Minimum confidence to accept result
VISION_CACHE_ENABLED=true             # Cache results by image hash
VISION_OLLAMA_URL=http://localhost:11434  # For local Ollama
VISION_OLLAMA_MODEL=qwen2-vl:7b
```

---

## 8. API Specification (Draft)

### Health Check
```
GET /api/health
Response: { "status": "ok", "version": "2.0.0" }
```

### Sync Favorites
```
POST /api/sync
Response: { "task_id": "sync-xxx", "status": "pending" }

GET /api/sync/status?task_id=sync-xxx
Response: { "status": "running|completed|failed", "progress": 50, "result": {...} }
```

### Rename Shinagaki
```
POST /api/rename
Response: { "task_id": "rename-xxx", "status": "pending" }

GET /api/rename/status?task_id=rename-xxx
Response: { "status": "running|completed|failed", "renamed_count": 15 }
```

### Generate Report
```
GET /api/monitor?event=C107&colors=color-1,color-2
Response: { "report_urls": ["..."] }
```

### Query Circles
```
GET /api/circles?event=C107&booth=水&search=xxx
Response: { "circles": [...], "total": 150 }
```

### List Shinagaki
```
GET /api/shinagaki?event=C107&status=processed|raw
Response: { "files": [...], "total": 85 }
```

### Migrate CSV
```
POST /api/migrate
Request: { "csv_url": "https://..." } or upload CSV file
Response: { "imported_count": 500 }
```

### Recognize Shinagaki Image
```
POST /api/recognize
Request: image file (multipart) or { "image_url": "https://..." }
Response: {
  "task_id": "recognize-xxx",
  "status": "pending"
}

GET /api/recognize/status?task_id=recognize-xxx
Response: {
  "status": "completed",
  "result": {
    "booth": "水 西あ52ab",
    "circle_name": "社团名",
    "author": "作者名",
    "event": "ComiC107",
    "twitter_id": "username",
    "confidence": 0.92,
    "raw_text": "..."
  }
}

POST /api/recognize/batch
Request: [image1, image2, ...]
Response: { "task_id": "batch-xxx", "count": 10, "status": "pending" }
```

---

## 9. Open Questions

| # | Question | Impact |
|---|----------|--------|
| 1 | Use SQLite in container or external PostgreSQL? | Architecture complexity |
| 2 | Cookie import vs noVNC for login? | User experience |
| 3 | Direct R2 upload from browser or via API? | File flow design |
| 4 | Task queue: simple threading or Redis/Celery? | Operational complexity |
| 5 | Dashboard: Streamlit (quick) or custom frontend (flexible)? | Development time |
| 6 | Multi-user support or single-user service? | Authentication design |
| 7 | Vision model: cloud API (GPT-4o/Qwen-VL) or local Ollama? | Cost vs privacy, GPU requirement |
| 8 | Confidence threshold for auto-accept vs manual review? | Accuracy vs automation rate |
| 9 | Batch recognition: async queue or synchronous? | UX and resource usage |

---

## 10. Glossary

| Term | Definition |
|------|------------|
| Comike | Japanese doujinshi exhibition series |
| Shinagaki (品書) | Menu/flyer distributed by circles at events |
| Circle | Doujin circle (creator group) |
| Circle.ms | Web platform for Comike catalog management |
| Web Catalog | Circle.ms's online catalog system |
| R2 | Cloudflare's S3-compatible object storage service |
| Headless | Browser running without GUI |
| Vision LLM | Large language model with image understanding (multimodal) |
| Qwen-VL | Alibaba's vision-language model, optimized for Chinese/Japanese |
| Ollama | Local LLM runtime for running models like Qwen2-VL, LLaVA |
| Presigned URL | Time-limited URL for accessing private R2 objects |

---

## 11. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-19 | TR-Ozipin | Initial PRD, v1.0 architecture documented, v2.0 roadmap defined |
| 1.1 | 2026-05-19 | TR-Ozipin | Added FR-11 Shinagaki Vision Recognition, Phase 6, vision API spec, env vars |

---

**Document Status**: Draft
**Next Review**: After Phase 1 completion
