# chessclub-web

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)

A Flask web portal for visualizing Chess.com club statistics — tournaments, leaderboards, head-to-head matchups, attendance tracking, and club records.

Built on top of the [`chessclub`](https://github.com/cmellojr/chessclub) Python library.

## Features

- **Club Overview** — member count, country, founding date
- **Member List** — all club members with ratings and titles
- **Tournaments** — full tournament history with results
- **Leaderboard** — player rankings computed from tournament results, filterable by year/month
- **Matchups** — head-to-head win/draw/loss records between members
- **Attendance** — participation percentages and streak tracking
- **Records** — notable club records (highest rating, best streak, etc.)
- **Rating History** — per-player rating evolution across club tournaments
- **Background Sync** — automatic data synchronization via APScheduler with permanent SQLite storage
- **Admin Dashboard** — manage watched clubs, trigger syncs, monitor progress

## Quick Start

### Prerequisites

- Python 3.11+
- (Optional) Chess.com server cookies for authenticated data

### Installation

```bash
git clone https://github.com/cmellojr/chessclub-web.git
cd chessclub-web
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env` with your values. At minimum, set `SECRET_KEY` and `ADMIN_PASSWORD`. For full functionality (tournaments, leaderboard, etc.), configure the Chess.com server cookies — see `.env.example` for detailed instructions.

### Run

```bash
python run.py
```

Open http://localhost:5000.

## Architecture

```
Chess.com API  →  chessclub library (SQLite cache, TTL-based)
                         ↓
               SQLAlchemy DB (permanent storage)
                         ↓
                   Flask routes (DB-first, library fallback)
```

The app uses a **two-layer data strategy**:

1. The `chessclub` library fetches data from Chess.com's API and caches it in a TTL-based SQLite cache.
2. A background sync worker periodically persists this data to a permanent SQLAlchemy database.
3. Routes serve data from the permanent DB first. For non-watched clubs, they fall back to live API calls via the library.

This ensures watched clubs remain accessible even when Chess.com cookies expire.

### Background Sync

- **Phase 1** (automatic): Syncs club overview, members, tournaments, results, leaderboard, and attendance on a configurable interval.
- **Phase 2** (manual): Fetches game archives per tournament. Incremental — only processes new tournaments. Computes matchups and records after completion.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask session secret |
| `ADMIN_PASSWORD` | Yes | Password for `/admin` dashboard |
| `CHESSCOM_SERVER_ACCESS_TOKEN` | For sync | Chess.com `ACCESS_TOKEN` cookie |
| `CHESSCOM_SERVER_PHPSESSID` | For sync | Chess.com `PHPSESSID` cookie |
| `CHESSCOM_OAUTH_CLIENT_ID` | Optional | For OAuth PKCE user login |
| `OAUTH_REDIRECT_URI` | Optional | OAuth callback URL |
| `SYNC_INTERVAL_HOURS` | Optional | Sync interval (default: 6) |
| `DATABASE_URI` | Optional | SQLAlchemy URI (default: `sqlite:///chessclub.db`) |

See [`.env.example`](.env.example) for full documentation.

## Development

```bash
# Install chessclub library in editable mode (local development)
pip install -e ../chessclub

# Lint and format
ruff check --fix .
ruff format .
```

Code follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html). Ruff enforces style rules — see [`pyproject.toml`](pyproject.toml) for configuration.

## Tech Stack

- **Backend**: Flask 3.0, Flask-SQLAlchemy, APScheduler
- **Frontend**: Bootstrap 5.3 (CDN), Jinja2 templates
- **Database**: SQLite (via SQLAlchemy)
- **Library**: [`chessclub`](https://github.com/cmellojr/chessclub) for Chess.com API integration

## License

[MIT](LICENSE) — Carlos Mello Jr
