# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
pip install -r requirements.txt   # or: pip install -e ../chessclub (local dev)
cp .env.example .env              # then fill in values

# Run
python run.py                     # Flask dev server at http://localhost:5000

# Lint & format
ruff check --fix .
ruff format .
```

No test suite exists yet.

## Architecture

Flask web portal for chess club statistics, built on the `chessclub` library (sibling repo at `../chessclub`).

**App factory**: `run.py` → `app/__init__.py` (`create_app`) → 4 blueprints:
- `app/auth.py` — Chess.com OAuth 2.0 PKCE flow + cookie fallback
- `app/club.py` — Club pages (overview, members, tournaments, leaderboard, matchups, attendance, records)
- `app/player.py` — Player pages (rating history)
- `app/admin.py` — Admin dashboard (sync management, watched clubs)

**Data flow** (two-layer caching):
```
Chess.com API → chessclub library (SQLite cache, TTL-based)
                        ↓
              SQLAlchemy DB (permanent storage)
                        ↓
                  Flask routes
```

Routes use **DB-first, library fallback**: `db_service.get_X()` returns data instantly from DB; if `None`, falls back to live `chessclub` library call. This means watched clubs work even when library cache expires or cookies are invalid.

**Key modules:**
- `app/chess_service.py` — `make_client(session)` and `is_authenticated(session)`: single source of truth for auth
- `app/db_service.py` — Read/write functions for the SQLAlchemy DB; read functions return `chessclub` library dataclass instances so templates need no changes
- `app/sync.py` — APScheduler background worker with two phases:
  - Phase 1 (automatic, every N hours): club, members, tournaments, results → persisted to DB
  - Phase 2 (manual per-club): game archives tournament-by-tournament → persisted to DB; computes records after completion
- `app/models.py` — 6 SQLAlchemy models mapping 1:1 to library dataclasses
- `app/extensions.py` — Shared `db = SQLAlchemy()` instance

## Code Style

Follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html):

- **Docstrings**: Google convention — one-line summary, `Args:`, `Returns:`, `Raises:` sections
- **Type annotations**: All function signatures must have parameter and return type annotations
- **Imports**: stdlib → third-party → local, enforced by `ruff` isort rules
- **Naming**: `snake_case` functions/variables, `CamelCase` classes, `UPPER_CASE` constants
- **Ruff** with 80-char line length, rules: E, W, F, I, N, UP, D (see `pyproject.toml`)
- Python 3.11+ — uses `X | Y` union syntax, `datetime.UTC`
- **Frontend**: Bootstrap 5.3 via CDN + Jinja2 templates — no JS build step
- All user-facing text in English

## chessclub Library

Import paths:
- `from chessclub.providers.chesscom import ChessComClient, ChessComCookieAuth, ChessComOAuth`
- `from chessclub.core.exceptions import ChessclubError, AuthenticationRequiredError`
- Services: `chessclub.services.{club,leaderboard,matchup,attendance,records,rating_history}_service`
- Core models (dataclasses): `Club, Member, Tournament, TournamentResult, Game, PlayerStats, Matchup, AttendanceRecord, ClubRecord, RatingSnapshot`

Public API (no auth): club overview, member list. Everything else requires server cookie auth.

## Environment Variables

Required for full functionality (see `.env.example`):
- `SECRET_KEY`, `ADMIN_PASSWORD`
- `CHESSCOM_SERVER_ACCESS_TOKEN`, `CHESSCOM_SERVER_PHPSESSID` — browser cookies from chess.com (expire ~24h/~2wk)
- `CHESSCOM_OAUTH_CLIENT_ID`, `OAUTH_REDIRECT_URI` — optional OAuth PKCE
- `SYNC_INTERVAL_HOURS` (default 6), `DATABASE_URI` (default `sqlite:///chessclub.db`)

## Branching

- `main` — stable releases
- `feature/*` — feature branches
