# AGENTS.md

This file provides guidance to AI coding agents (Codex, Jules, Copilot, Cursor, etc.) when working with this repository.

## Quick Reference

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env              # fill in values

# Run
python run.py                     # http://localhost:5000

# Lint & format (must pass before committing)
ruff check --fix .
ruff format .
```

There is no test suite yet. Verify changes by running `ruff check . && ruff format --check .`.

## Project Overview

Flask web portal for chess club statistics, powered by the [`chessclub`](https://github.com/cmellojr/chessclub) Python library. Displays tournaments, leaderboards, matchups, attendance, and records for Chess.com clubs.

## Architecture

```
run.py → app/__init__.py (create_app factory) → 4 blueprints
                │
                ├── app/auth.py      — Chess.com OAuth 2.0 PKCE + cookie fallback
                ├── app/club.py      — Club pages (overview, members, tournaments, ...)
                ├── app/player.py    — Player pages (rating history)
                └── app/admin.py     — Admin dashboard (sync management)
```

### Data Flow (two-layer caching)

```
Chess.com API  →  chessclub library (SQLite cache, TTL)
                         ↓
               SQLAlchemy DB (permanent)
                         ↓
                   Flask routes
```

Routes use a **DB-first, library fallback** pattern:
- `db_service.get_X(slug)` returns data from the permanent DB.
- If the club is in the DB (watched club), always serve from DB — never fall back to the library.
- If the club is NOT in the DB (non-watched), fall back to the `chessclub` library for a live API call.

### Key Modules

| Module | Purpose |
|--------|---------|
| `app/chess_service.py` | `make_client(session)`, `is_authenticated(session)` — auth single source of truth |
| `app/db_service.py` | Read/write functions for SQLAlchemy DB; returns `chessclub` library dataclass instances |
| `app/sync.py` | APScheduler background worker (Phase 1: auto sync; Phase 2: manual game archives) |
| `app/models.py` | 6 SQLAlchemy ORM models mapping 1:1 to library dataclasses |
| `app/extensions.py` | Shared `db = SQLAlchemy()` instance |
| `config.py` | All settings loaded from environment variables via `python-dotenv` |

### Background Sync

- **Phase 1** (automatic, every N hours): club overview, members, tournaments, results, leaderboard, attendance → persisted to DB.
- **Phase 2** (manual, per-club): game archives per tournament → persisted to DB; recomputes records after completion. Incremental — skips tournaments already stored.

## Code Conventions

- **Style**: Google Python Style Guide (docstrings, imports, types).
- **Linter**: Ruff — 80-char line length, rules: E, W, F, I, N, UP, D (Google convention). Config in `pyproject.toml`.
- **Python**: 3.11+ (uses `X | Y` union syntax, `datetime.UTC`).
- **Frontend**: Bootstrap 5.3 via CDN + Jinja2 templates. No JavaScript build step.
- **Language**: All user-facing text in English.
- **Commits**: Conventional-style messages — short imperative summary, no prefix required.

## Dependencies

Runtime dependencies are in `requirements.txt`. The `chessclub` library is installed from GitHub by default; for local development, use `pip install -e ../chessclub`.

## Environment Variables

See `.env.example` for full documentation. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask session secret |
| `ADMIN_PASSWORD` | Yes | Admin dashboard access |
| `CHESSCOM_SERVER_ACCESS_TOKEN` | For sync | Chess.com browser cookie |
| `CHESSCOM_SERVER_PHPSESSID` | For sync | Chess.com browser cookie |
| `CHESSCOM_OAUTH_CLIENT_ID` | Optional | OAuth PKCE for user login |
| `SYNC_INTERVAL_HOURS` | No | Default: 6 |
| `DATABASE_URI` | No | Default: `sqlite:///chessclub.db` |

## Common Patterns

### Adding a new route that reads club data

```python
# In app/club.py — always follow DB-first pattern:
club = db_service.get_club(slug)
if club:
    data = db_service.get_X(slug)
    return render_template("...", data=data or [])

# Fallback for non-watched clubs:
client = chess_service.make_client(session)
data = SomeService(client).get_X(slug)
```

### Adding a new DB-backed field

1. Add column to the model in `app/models.py`.
2. Add upsert logic in `db_service.py` (write function).
3. Add read logic in `db_service.py` (read function returning library dataclass).
4. Persist in `app/sync.py` after fetching from library.

## File Structure

```
chessclub-web/
├── run.py                  # Dev server entry point
├── config.py               # Configuration from env vars
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Ruff config
├── watched_clubs.json      # Clubs monitored by sync worker
├── app/
│   ├── __init__.py         # App factory + Jinja2 filters
│   ├── extensions.py       # SQLAlchemy instance
│   ├── models.py           # ORM models
│   ├── db_service.py       # DB read/write layer
│   ├── chess_service.py    # Auth helpers
│   ├── sync.py             # Background sync worker
│   ├── auth.py             # Auth blueprint
│   ├── club.py             # Club blueprint
│   ├── player.py           # Player blueprint
│   ├── admin.py            # Admin blueprint
│   └── templates/          # Jinja2 templates (Bootstrap 5.3)
├── .env.example            # Environment variable documentation
├── CLAUDE.md               # Claude Code guidance
└── AGENTS.md               # This file
```
