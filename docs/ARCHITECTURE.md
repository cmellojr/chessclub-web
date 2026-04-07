# Architecture

This document describes the architecture of **chessclub-web**, a Flask web
portal for chess club statistics built on top of the
[chessclub](https://github.com/cmellojr/chessclub) library.

---

## High-Level Overview

```
                        ┌─────────────────────┐
                        │    Chess.com API     │
                        └──────────┬──────────┘
                                   │ HTTP
                                   ▼
                        ┌─────────────────────┐
                        │  chessclub library   │
                        │ (SQLite cache, TTL)  │
                        └──────────┬──────────┘
                                   │ Python dataclasses
              ┌────────────────────┼────────────────────┐
              │                    │                     │
              ▼                    ▼                     ▼
   ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
   │   sync worker    │ │    Flask app     │ │    admin panel   │
   │  (APScheduler)   │ │   (blueprints)   │ │   (dashboard)    │
   └────────┬─────────┘ └────────┬─────────┘ └──────────────────┘
            │                    │
            ▼                    ▼
   ┌──────────────────┐ ┌──────────────────┐
   │  db_service.py   │ │  db_service.py   │
   │  (write layer)   │ │  (read layer)    │
   └────────┬─────────┘ └────────┬─────────┘
            │                    │
            ▼                    ▼
   ┌─────────────────────────────────────────┐
   │       SQLAlchemy Database (SQLite)      │
   │       instance/chessclub.db             │
   └─────────────────────────────────────────┘
```

**Data flows through three paths:**

1. **Sync worker** fetches data from Chess.com via the chessclub library and
   persists it to the SQLAlchemy database.
2. **Flask routes** read from the database first (instant); if the club is not
   a watched club, they fall back to the chessclub library for live API calls.
3. **Admin panel** controls the sync worker, manages watched clubs, and
   displays sync progress.

---

## Application Factory

The entry point is `run.py`, which calls `create_app()` in `app/__init__.py`.
The factory follows the standard Flask pattern:

```
run.py
  └─ create_app()                          # app/__init__.py
       ├─ Config.from_object()             # config.py
       ├─ db.init_app() + db.create_all()  # app/extensions.py, app/models.py
       ├─ Register Jinja2 filters          # ts_to_date, ts_to_datetime, country_flag
       ├─ Register context processors      # inject_auth_status
       ├─ Register blueprints              # auth, club, player, admin
       └─ init_scheduler()                 # app/sync.py (APScheduler)
```

The scheduler is only started in the main Werkzeug process (not the reloader
child) to avoid duplicate jobs in debug mode.

---

## Blueprints

The application is organized into four Flask blueprints:

| Blueprint | Prefix | Module | Responsibility |
|-----------|--------|--------|----------------|
| `club` | `/` | `app/club.py` | Homepage, search, club pages (overview, members, tournaments, leaderboard, matchups, attendance, records) |
| `player` | `/player` | `app/player.py` | Player rating history |
| `auth` | `/auth` | `app/auth.py` | OAuth 2.0 PKCE login/callback/logout, setup page |
| `admin` | `/admin` | `app/admin.py` | Admin login, dashboard, watched clubs management, sync triggers |

### Route Map

```
GET  /                                → club.index
GET  /search?slug=...                 → club.search → redirect
GET  /club/<slug>                     → club.overview
GET  /club/<slug>/members             → club.members
GET  /club/<slug>/tournaments         → club.tournaments
GET  /club/<slug>/leaderboard         → club.leaderboard
GET  /club/<slug>/matchups            → club.matchups
GET  /club/<slug>/attendance          → club.attendance
GET  /club/<slug>/records             → club.records
GET  /player/<username>/rating-history → player.rating_history
GET  /auth/login                      → auth.login
GET  /auth/callback                   → auth.callback
GET  /auth/logout                     → auth.logout
GET  /auth/setup                      → auth.setup
GET  /admin/                          → admin.dashboard
POST /admin/login                     → admin.login
GET  /admin/logout                    → admin.logout
GET  /admin/clubs                     → admin.clubs
POST /admin/clubs/add                 → admin.add_club
POST /admin/clubs/remove              → admin.remove_club
POST /admin/sync                      → admin.trigger_sync
POST /admin/sync-games/<slug>         → admin.trigger_game_sync
```

---

## DB-First Route Pattern

All club and player routes follow a two-tier data resolution strategy:

```python
# 1. Try database first (watched clubs, instant)
club = db_service.get_club(slug)
if club:
    data = db_service.get_leaderboard(slug, ...)
    return render_template("...", data=data or [])

# 2. Fall back to chessclub library (non-watched clubs, live API)
client = chess_service.make_client(session)
data = LeaderboardService(client).get_leaderboard(slug, ...)
return render_template("...", data=data)
```

**Key design decisions:**

- **Watched clubs never fall back to the library.** If data is not yet synced,
  the template receives an empty list instead of making an API call that might
  fail with expired credentials.
- **Non-watched clubs** use the library directly, which requires valid
  authentication (OAuth or server cookies) for protected endpoints.
- Templates receive the same library dataclass instances regardless of the
  data source, so **zero template changes** are needed.

---

## Authentication

The application supports two complementary credential types, mirroring the
chessclub CLI:

### 1. Server Cookie Credentials (`.env`)

```
CHESSCOM_SERVER_ACCESS_TOKEN=...
CHESSCOM_SERVER_PHPSESSID=...
```

These are Chess.com session cookies obtained from a browser. They are
required for the internal web API (`/callback/` endpoints) used by
tournaments, leaderboard, and other protected features. These cookies
**expire every ~24 hours** and must be manually refreshed.

### 2. OAuth 2.0 PKCE (Per-User)

```
CHESSCOM_OAUTH_CLIENT_ID=...
OAUTH_REDIRECT_URI=http://localhost:5000/auth/callback
```

Users log in via Chess.com's OAuth flow. The access token is stored in the
Flask session. OAuth grants access to public API endpoints but **not** the
internal `/callback/` API.

### Credential Resolution

`chess_service.make_client(session)` resolves credentials in priority order:

1. **Server cookies + OAuth** — cookies as base auth, OAuth Bearer header
   injected on top.
2. **OAuth only** — public API access; internal endpoints return 403.
3. **No credentials** — public API only (club overview, member list).

### Session-Based OAuth Provider

`_SessionOAuthProvider` implements the `AuthProvider` interface from the
chessclub library, wrapping the Flask session's `oauth_token` dict. It
checks expiry with a 60-second safety buffer.

---

## Database Layer

### Extensions (`app/extensions.py`)

A single shared `SQLAlchemy()` instance initialized in the app factory.

### ORM Models (`app/models.py`)

Six models map 1:1 to chessclub library dataclasses:

```
ClubModel (clubs)
  ├─ MemberModel (members)              [composite PK: club_id + username]
  ├─ TournamentModel (tournaments)      [FK: club_slug → clubs.id]
  │    ├─ TournamentResultModel          [composite PK: tournament_id + player]
  │    └─ GameModel (games)              [auto-increment PK, FK: tournament_id]
  └─ ClubRecordModel (club_records)     [auto-increment PK, FK: club_id]
```

**Indexes:**
- `ix_games_tournament` on `games.tournament_id`
- `ix_games_players` on `games.white, games.black`

### Data Access Layer (`app/db_service.py`)

Separated into **write** and **read** functions:

**Write functions** (called by the sync worker):

| Function | Strategy |
|----------|----------|
| `upsert_club()` | INSERT or UPDATE by PK |
| `upsert_members()` | DELETE all + INSERT (full replace) |
| `upsert_tournaments()` | INSERT or UPDATE by PK |
| `upsert_results()` | INSERT or UPDATE by composite PK |
| `upsert_games()` | DELETE all for tournament + INSERT |
| `store_records()` | DELETE all for club + INSERT |

**Read functions** (called by routes):

| Function | Returns | Source |
|----------|---------|--------|
| `get_club()` | `Club` | Direct query |
| `get_members()` | `list[Member]` | Direct query |
| `get_tournaments()` | `list[Tournament]` | Direct query, ordered by end_date DESC |
| `get_leaderboard()` | `list[PlayerStats]` | **Computed** from results + tournaments (GROUP BY player) |
| `get_matchups()` | `list[Matchup]` | **Computed** from games + tournaments (GROUP BY player pair) |
| `get_attendance()` | `list[AttendanceRecord]` | **Computed** from results + tournaments (streaks + participation %) |
| `get_records()` | `list[ClubRecord]` | Direct query |
| `get_rating_history()` | `list[RatingSnapshot]` | **Computed** from results + tournaments |

All read functions return library dataclass instances or `None`, ensuring
templates need no changes.

---

## Background Sync Worker

The sync system is implemented in `app/sync.py` and uses APScheduler for
periodic execution.

### Two-Phase Architecture

**Phase 1 — Light data (automatic, periodic):**

Runs every `SYNC_INTERVAL_HOURS` (default: 6) hours via APScheduler.
Also triggered manually from the admin dashboard.

```
For each watched club:
  1. club_overview     → db_service.upsert_club()
  2. members           → db_service.upsert_members()
  3. tournaments       → db_service.upsert_tournaments()
  4. tournament_results → for each tournament:
                            db_service.upsert_results()
  5. leaderboard       → (library cache warming only)
  6. attendance         → (library cache warming only)
```

**Phase 2 — Game archives (manual, per-club):**

Triggered from the admin dashboard per club. Processes one tournament at a
time with real-time progress tracking.

```
For each finished tournament (incremental — skips already stored):
  1. client.get_tournament_games(t) → db_service.upsert_games()

After all tournaments:
  2. RecordsService.get_records()   → db_service.store_records()
```

### Incremental Sync

`db_service.has_games(tournament_id)` checks if a tournament's games are
already stored. Phase 2 skips these tournaments entirely, minimizing
HTTP requests to Chess.com.

### Sync Status Tracking

A module-level `sync_status` dict tracks progress in real time:

```python
sync_status = {
    "last_run": datetime | None,
    "running": bool,
    "clubs": {
        "club-slug": {
            "ok": bool,
            "error": str | None,
            "synced_at": datetime | None,
            "steps": {"club_overview": "ok", "members": "ok", ...},
            "game_sync": {
                "running": bool,
                "total": int,
                "done": int,
                "current": str | None,
                "errors": list[str],
                "completed_at": datetime | None,
            },
        },
    },
}
```

This dict is injected into all templates via the `inject_auth_status`
context processor. The admin dashboard auto-refreshes (5-second interval)
while any sync is running.

### Threading Model

Both Phase 1 and Phase 2 syncs run in daemon threads started via
`threading.Thread`. The APScheduler `BackgroundScheduler` also runs in its
own daemon thread. All sync threads use `app.app_context()` for database
access.

---

## Frontend

### Template Hierarchy

```
base.html                          (navbar, flash messages, footer)
  ├─ index.html                    (club search form)
  ├─ club/
  │    ├─ _nav.html                (club sub-navigation, included by all club pages)
  │    ├─ overview.html
  │    ├─ members.html
  │    ├─ tournaments.html
  │    ├─ leaderboard.html
  │    ├─ matchups.html
  │    ├─ attendance.html
  │    └─ records.html
  ├─ player/
  │    └─ rating_history.html
  ├─ auth/
  │    └─ setup.html
  └─ admin/
       ├─ login.html
       ├─ dashboard.html
       └─ clubs.html
```

### Technology Stack

- **CSS framework:** Bootstrap 5.3 via CDN — no build steps
- **Templating:** Jinja2 with custom filters (`ts_to_date`, `ts_to_datetime`,
  `country_flag`)
- **JavaScript:** Bootstrap bundle only (no custom JS framework)

### Custom Jinja2 Filters

| Filter | Input | Output |
|--------|-------|--------|
| `ts_to_date` | Unix timestamp | `DD/MM/YYYY` |
| `ts_to_datetime` | Unix timestamp | `DD/MM/YYYY HH:MM` |
| `country_flag` | Chess.com country URL | Flag emoji + country code (e.g., `🇧🇷 BR`) |

---

## Configuration

All configuration is loaded from environment variables via `config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-secret-change-in-production` | Flask secret key |
| `CHESSCOM_OAUTH_CLIENT_ID` | `""` | Chess.com OAuth app client ID |
| `OAUTH_REDIRECT_URI` | `http://localhost:5000/auth/callback` | OAuth callback URL |
| `CHESSCOM_SERVER_ACCESS_TOKEN` | `""` | Chess.com session cookie |
| `CHESSCOM_SERVER_PHPSESSID` | `""` | Chess.com session cookie |
| `SYNC_INTERVAL_HOURS` | `6` | Hours between automatic syncs |
| `WATCHED_CLUBS_FILE` | `watched_clubs.json` | Path to the club list file |
| `ADMIN_PASSWORD` | `""` | Admin panel password (disabled if empty) |
| `DATABASE_URI` | `sqlite:///chessclub.db` | SQLAlchemy database URI |

---

## Dependency on the chessclub Library

The application depends on the
[chessclub](https://github.com/cmellojr/chessclub) library for all
Chess.com API communication. Key integration points:

| Component | chessclub API |
|-----------|---------------|
| `chess_service.py` | `ChessComClient`, `ChessComCookieAuth`, `AuthProvider`, `AuthCredentials` |
| `club.py` | `ClubService`, `LeaderboardService`, `MatchupService`, `AttendanceService`, `RecordsService` |
| `player.py` | `RatingHistoryService` |
| `sync.py` | `ChessComClient`, `ChessComCookieAuth`, `ClubService`, `LeaderboardService`, `AttendanceService`, `RecordsService` |
| `db_service.py` | Dataclass imports: `Club`, `Member`, `Tournament`, `TournamentResult`, `Game`, `ClubRecord`, `Matchup`, `PlayerStats`, `AttendanceRecord`, `RatingSnapshot` |

The library provides:
- HTTP client with built-in SQLite cache (see [CACHE.md](CACHE.md))
- Service classes that parse Chess.com API responses into typed dataclasses
- Cookie and OAuth authentication providers

---

## Security Considerations

- **Admin panel** is password-protected via `ADMIN_PASSWORD` env var.
  Disabled entirely when the variable is empty.
- **OAuth tokens** are stored in the Flask session (server-side signed cookie).
  The `_SessionOAuthProvider` checks expiry with a 60-second buffer.
- **Server cookies** (`ACCESS_TOKEN`, `PHPSESSID`) are never exposed to
  clients — they remain in server-side `.env` configuration.
- **CSRF protection** is not implemented (all state-changing admin routes use
  POST, but no token verification).
- **Exception handling** catches broad `Exception` in routes to prevent
  internal error details from leaking to users.
