# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sherlock Homes is a real estate aggregation platform for Medellín, Colombia. It scrapes multiple real estate agency websites, stores listings in SQLite, and presents them through a filterable web interface with map visualization.

## Commands

### Development Server
```bash
source backend/venv/bin/activate
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Backend tests (from project root, with venv activated)
pytest -n auto

# Single backend test file
pytest backend/tests/test_alberto_alvarez.py -v

# Frontend tests
cd frontend && npm test
```

### Setup
```bash
pip install -r backend/requirements.txt
playwright install chromium
pre-commit install
```

### Linting (runs automatically via pre-commit)
- Python: ruff (with `--fix`)
- Frontend: prettier

## Architecture

### Backend Structure
- **FastAPI app** (`backend/main.py`): REST API with `/api/properties`, `/api/properties/locations`, `/api/scrape/batch` endpoints
- **Database** (`backend/database.py`): SQLAlchemy models with soft delete pattern (`deleted_at` column)
- **Scraper orchestration** (`backend/scraper.py`): Coordinates parallel execution of all scrapers via `asyncio.gather()`
- **Storage layer** (`backend/storage.py`): Handles property persistence and deduplication

### Scraper Pattern
All scrapers inherit from `BaseScraper` (`backend/scrapers/base.py`) and implement:
1. `get_search_inputs()` - Returns list of (url, metadata) tuples
2. `process_search_inputs()` - Extracts property links from search pages
3. `extract_property_details()` - Parses individual property pages

Key conventions:
- Use `UNIFIED_BARRIOS` dict to map agency-specific neighborhood codes to standardized names
- Filter out logo/icon images from galleries
- Extract GPS coordinates when available (check `window` objects, map iframes)
- Concurrency controlled via `asyncio.Semaphore` (typically 3-5 concurrent pages)

### Adding a New Scraper
Detailed guide at `backend/scrapers/ADDING_NEW_SCRAPER.md`. Summary:
1. Create `backend/scrapers/new_site.py` extending `BaseScraper`
2. Create `backend/tests/test_new_site.py` with `test_search_results` and `test_single_property`
3. Register in `backend/scraper.py` (import + helper function + add to `scrape_all_batch`)
4. Add endpoint case in `backend/main.py`
5. Add option to `#websiteSelect` dropdown in `frontend/index.html`
6. Add source name mapping in `frontend/utils.js`
7. Download favicon: `curl -L -A "Mozilla/5.0" "https://www.google.com/s2/favicons?domain=DOMAIN&sz=64" -o frontend/assets/images/icons/source_name.png`

### Frontend Structure
- Vanilla JavaScript (no framework)
- Modules in `frontend/modules/`: `api.js`, `dom.js`, `filters.js`, `map.js`
- Tests use Vitest with happy-dom

## Configuration

- Ruff ignores: E711 (SQLAlchemy None comparisons), E402, E722
- Scrape cooldown: 120 minutes (configurable in `main.py`)
- Database: SQLite at `./real_estate.db`
