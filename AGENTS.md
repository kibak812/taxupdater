# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Korean tax law monitoring system - automated crawling of tax rulings, precedents, and interpretations from 6 government sources with real-time notifications.

**Target Sites:**
- Tax Tribunal (조세심판원)
- NTS Authority Interpretations (국세청 유권해석)
- NTS Precedents (국세청 판례)
- Ministry of Economy (기획재정부)
- Ministry of Interior (행정안전부)
- Board of Audit (감사원)

## Essential Commands

```bash
# Windows venv activation
taxupdater_venv\Scripts\activate

# Linux/Mac venv activation
source taxupdater_venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run web server (development)
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8001 --reload
```

## Architecture

### Hexagonal Architecture (Ports & Adapters)

```
src/
├── core/                    # Domain core (no external dependencies)
│   ├── domain/              # Value objects (CrawlResult, SiteDefinition)
│   └── ports/               # Interfaces (ICrawler, IRepository, INotificationChannel)
├── crawlers/                # Port implementations
│   ├── nts_base_crawler.py  # Template Method pattern base
│   ├── legacy_adapter.py    # Adapts function-based crawlers to ICrawler
│   └── *_crawler.py         # Site-specific implementations
├── services/
│   └── scheduler_service.py # APScheduler-based auto crawling
├── repositories/            # Data persistence (SQLite)
├── web/                     # FastAPI application
│   └── app.py               # Main application, API endpoints & WebSocket
└── config/
    ├── settings.py          # URLs, columns, key columns per site
    └── sites.py             # SITE_CATALOG, SITE_DISPLAY mappings
```

### Key Design Patterns

1. **Template Method** (`nts_base_crawler.py`): NTS crawlers share common logic
2. **Adapter** (`legacy_adapter.py`): Wraps legacy function crawlers as ICrawler
3. **Strategy** (notifications): Email/WebSocket channels implement INotificationChannel
4. **Repository**: SQLite with Excel backup, abstracts persistence

### Data Flow

```
Scheduler → CrawlOrchestrator → ICrawler.crawl() → IRepository.save()
                    ↓                                     ↓
            Detect new entries                    SQLite + Excel backup
                    ↓
          INotificationDispatcher.dispatch()
```

## Key Technical Details

### Database (SQLite)

- Location: `data/tax_data.db`
- Key column per site defines uniqueness (e.g., "문서번호", "청구번호")
- Use `INSERT OR IGNORE` for duplicate handling
- Timestamps auto-injected at repository level

### WebSocket Progress

```python
# Correct: use .value attribute
progress.value = percentage

# Wrong: dictionary-style access
progress['value'] = percentage
```

### Site-specific Crawling Notes

**Ministry of Interior (행정안전부)**: Requires `upperMenuId` parameter or redirects to login:
```python
# Correct URL
"https://www.olta.re.kr/...?menuNo=9020000&upperMenuId=9000000"
```

**Board of Audit (감사원)**: Requires dropdown selection before search button click.

### API Route Order

FastAPI requires specific routes before wildcards:
```python
@app.post("/api/crawl/all")        # First
@app.post("/api/crawl/{site_key}") # Second
```

### Link Generation

NTS links use search-based URLs (not direct document IDs):
```python
from src.utils.link_generator import generate_nts_search_link
link = generate_nts_search_link(doc_number, "authority")
```

## Configuration

### Site Settings (`src/config/settings.py`)

```python
URLS = {"site_key": "https://..."}
DATA_COLUMNS = {"site_key": ["col1", "col2", ...]}
KEY_COLUMNS = {"site_key": "primary_key_column"}
```

### Crawling Limits

```python
CRAWLING_CONFIG = {
    "max_pages": 20,
    "max_items": 5000,
    "retry_count": 3,
    "timeout": 10
}
```

## Development Guidelines

- Read files before modifying them
- No emojis in code (per user preference)
- Consider modularization for files exceeding 500 lines
- Web-only environment (no tkinter dependencies)
- Always verify column existence before DataFrame access

## Documentation

- [Technical Details](docs/TECHNICAL_DETAILS.md): SQLite, WebSocket, crawler specifics
- [Changelog](docs/CHANGELOG.md): Development history
- [Deployment](docs/DEPLOYMENT.md): LocalTunnel, systemd setup
- [Troubleshooting](docs/TROUBLESHOOTING.md): Common issues
