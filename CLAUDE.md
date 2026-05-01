# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based property recommendation system that scrapes rental listings from 591.com.tw (rent.591.com.tw), stores them in a local SQLite database, and sends personalized daily recommendations via LINE Notify based on the user's view history.

## Production

**Railway 部署網址：** https://8591recommender-production.up.railway.app/

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Edit .env and set LINE_NOTIFY_TOKEN
```

## Commands

```bash
# Run a one-off scrape + recommend + notify cycle
python main.py run

# Start the scheduler (runs daily at 09:00)
python main.py start

# Record a manually viewed property (by 591 numeric ID)
python main.py view <property_id>

# Debug scraper — saves raw HTML to debug_page.html and probes CSS selectors
python debug_scraper.py
```

There are no tests, linter configs, or CI setup in this repository.

## Architecture

The system is a linear pipeline orchestrated by `scheduler/daily_job.py`:

```
scraper → database → recommender → notifier
```

**scraper/** — Playwright headless Chromium drives `rent.591.com.tw/list`, renders the JS-heavy page, then BeautifulSoup/lxml parses `.recommend-ware` cards. `browser.py` is a thin async context manager wrapping Playwright. `property_scraper.py` contains the URL builder, HTML parser (`_parse_listing`), and `save_listings` (upsert logic with same-batch deduplication).

**database/** — SQLAlchemy with a module-level engine/session factory. `init_db()` runs `create_all` (schema-from-models, no migrations via Alembic despite it being installed). `get_db()` is a `@contextmanager` that commits on clean exit and rolls back on exception. Four models: `Property`, `ViewLog`, `Recommendation`, `UserPreference`.

**recommender/** — Content-based filtering. `feature_extractor.py` converts a `Property` ORM object into an 8-element `float32` numpy vector `[price_norm, area_norm, rooms, living_rooms, bathrooms, floor_norm, region_enc, type_enc]` with fixed normalization ranges (e.g., price capped at 100k). `build_user_profile` computes a linearly time-weighted average of the user's recent 30-day view history. `similarity.py` then does a batch `cosine_similarity` (sklearn) against all un-viewed active properties, filters by `SIMILARITY_THRESHOLD`, and saves `Recommendation` rows.

**notifier/** — `line_notify.py` POSTs to the LINE Notify API via `httpx`. Each recommendation is sent as a separate message with an optional thumbnail image.

**scheduler/** — `daily_job.py` is a plain `async def` that runs the three pipeline steps in sequence. `main.py` wraps this with APScheduler (cron trigger at 09:00).

## Configuration

All tunable settings live in `config/settings.py`, sourced from `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///591.db` | SQLAlchemy DB URL |
| `LINE_NOTIFY_TOKEN` | — | Required for notifications |
| `MAX_PAGES_PER_SEARCH` | `5` | Pages fetched per scrape run |
| `TOP_N_RECOMMENDATIONS` | `10` | Max recommendations sent |
| `SIMILARITY_THRESHOLD` | `0.3` | Min cosine similarity to qualify |

Search parameters (region, price range, area range) are in `DEFAULT_SEARCH_PARAMS` at the bottom of `config/settings.py`. Region codes come from `REGION_CODES` in `scraper/property_scraper.py`.

## Key Conventions

- All async code uses `asyncio`; the scraper is async, the recommender and notifier are sync. `run_daily_job` is `async def` and bridges them.
- The DB session is never passed across module boundaries — each module calls `get_db()` directly.
- `Property.features` stores the raw label list as a Python `str(list)` (not JSON), so parsing it back requires `ast.literal_eval`.
- When the user has no view history, `compute_recommendations` falls back to returning the most recently scraped properties (score=1.0, reason="最新上架").
- `debug_scraper.py` targets `rent.591.com.tw` (same as the real scraper), saves raw HTML to `debug_page.html`, and probes a list of CSS selectors — useful when the site structure changes and `.recommend-ware` stops matching.
