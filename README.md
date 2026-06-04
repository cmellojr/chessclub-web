# chessclub-web

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)

A Flask web portal for Chess.com club statistics — tournaments, leaderboards, matchups, attendance, and records.

Built on the [`chessclub`](https://github.com/cmellojr/chessclub) Python library.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Open http://localhost:5000. See [`.env.example`](.env.example) for configuration options.

## Architecture

```
Chess.com API → chessclub library → SQLAlchemy DB → Flask routes (DB-first, library-fallback)
```

Two-tier cache + background sync. See [`docs/architecture.md`](docs/architecture.md) and [`docs/cache.md`](docs/cache.md).

## Features

Overview, Members, Tournaments, Leaderboard, Matchups, Attendance, Records, Rating History, Background Sync, Admin Dashboard. See [`docs/FEATURE-MAP.md`](docs/FEATURE-MAP.md).

## Tech Stack

**Backend:** Flask 3.0, Flask-SQLAlchemy, APScheduler  
**Frontend:** Bootstrap 5.3 (CDN), Jinja2  
**Database:** SQLite via SQLAlchemy  
**Library:** [`chessclub`](https://github.com/cmellojr/chessclub)

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). AI coding agents see [`AGENTS.md`](AGENTS.md).

## License

[MIT](LICENSE) — Carlos Mello Jr
