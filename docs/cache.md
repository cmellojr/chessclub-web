# Cache System

This document describes the two-tier caching architecture used in
**chessclub-web**: the chessclub library's built-in SQLite cache and the
application's SQLAlchemy persistence layer.

---

## Overview

```
Chess.com API
      │
      ▼
┌───────────────────────────────────────────────┐
│  Tier 1: chessclub Library Cache              │
│  ~/.cache/chessclub/cache.db                  │
│  SQLite · TTL-based · transparent · volatile  │
└───────────────────────┬───────────────────────┘
                        │ Python dataclasses
                        ▼
┌───────────────────────────────────────────────┐
│  Tier 2: SQLAlchemy Database                  │
│  instance/chessclub.db                        │
│  SQLite · permanent · populated by sync       │
└───────────────────────────────────────────────┘
                        │
                        ▼
                  Flask routes
```

**Why two tiers?**

The chessclub library cache is designed for CLI usage where sessions are
short-lived. Its TTLs (30 minutes to 30 days) work well for interactive
queries but cause data loss when entries expire — and the Chess.com server
cookies needed to re-fetch data expire every ~24 hours. If cookies expire
before the cache is refreshed, **all cached data is lost**.

The SQLAlchemy persistence layer solves this by storing data permanently.
The sync worker populates it periodically, and routes read from it
instantly regardless of library cache state.

---

## Tier 1: chessclub Library Cache

### Storage

- **Location:** `~/.cache/chessclub/cache.db`
- **Engine:** SQLite with WAL (Write-Ahead Logging) journal mode
- **Schema:**

```sql
CREATE TABLE cache (
    key        TEXT PRIMARY KEY,   -- full URL + serialized query params
    expires_at REAL NOT NULL,      -- Unix timestamp (insertion time + TTL)
    body       TEXT NOT NULL       -- JSON-serialized HTTP response body
);
CREATE INDEX idx_expires ON cache (expires_at);
```

### Cache Key Format

Each key is the full request URL with query parameters serialized via
`json.dumps(params, sort_keys=True)`, ensuring consistent keys for
identical requests regardless of parameter order.

### TTL Rules

The library assigns TTLs based on URL patterns, calibrated to real-world
Chess.com data volatility:

| Data Type | URL Pattern | TTL | Rationale |
|-----------|------------|-----|-----------|
| Public tournament data | `/pub/tournament/…` | 7 days | Finished tournaments are immutable |
| Past game archives | `/games/{year}/{month}` (past) | 30 days | Historical game archives never change |
| Current month archives | `/games/{year}/{month}` (current) | 1 hour | Active tournaments have ongoing rounds |
| Player profile | `/pub/player/{username}` | 24 hours | Ratings update once daily at most |
| Club member list | `/pub/club/{slug}/members` | 1 hour | Joins/leaves are infrequent |
| Club metadata | `/pub/club/{slug}` | 24 hours | Name/description rarely change |
| Tournament leaderboard | `*/leaderboard` | 7 days | Final standings are immutable |
| Club tournament list | `/clubs/live/past/{id}` | 30 minutes | New tournaments appear weekly |

The `_cache_ttl(url)` static method on `ChessComClient` evaluates patterns
in order; the first match wins. URLs with no matching pattern are not
cached (e.g., authentication endpoints).

### How It Works

All HTTP requests in `ChessComClient` go through `_cached_get()`:

```
_cached_get(url, **kwargs)
  │
  ├─ URL has no cacheable TTL? ──→ network request (uncached)
  │
  ├─ Cache HIT (not expired)? ──→ return CachedResponse immediately
  │
  └─ Cache MISS or expired?
       │
       ├─ Network request
       │
       ├─ HTTP 200 → cache.set(key, body, ttl) → return response
       ├─ HTTP 404 → cache.set(key, {_status: 404}, ttl) → return response
       └─ HTTP 401/429/5xx → pass through (NOT cached)
```

**Important behaviors:**
- **404 responses are cached** to avoid repeated probes (e.g., during
  leaderboard URL fallback attempts).
- **Error responses (401, 429, 5xx) are never cached**, ensuring retries
  have a chance to succeed.
- **Cache failures are silent** — all database operations are wrapped in
  try-except blocks. A corrupt or missing cache file never breaks the
  application.

### `CachedResponse` Object

When data is served from cache, the library returns a lightweight
`CachedResponse` stub that mimics `requests.Response`:

- `status_code`: defaults to 200, unless `_status` was stored (e.g., 404)
- `json()`: returns the cached body dict
- `raise_for_status()`: no-op

This allows caller code to handle cached and live responses identically.

### Expiration and Invalidation

**Lazy expiration:** stale entries are deleted on first read after TTL
elapses. There is no background cleanup process.

**Manual invalidation:**

```bash
# CLI commands (from the chessclub library)
chessclub cache clear              # Delete all entries
chessclub cache clear --expired    # Delete only expired entries
chessclub cache stats              # Show cache statistics

# Or delete the file directly
rm ~/.cache/chessclub/cache.db
```

### Cache Statistics

`ChessComClient` tracks `cache_hits` and `network_requests` counters per
session. The chessclub CLI's verbose mode (`-v`) displays these counts.

---

## Tier 2: SQLAlchemy Persistence Layer

### Storage

- **Location:** `instance/chessclub.db` (relative to the Flask app root)
- **Engine:** SQLite via Flask-SQLAlchemy
- **URI:** configurable via `DATABASE_URI` environment variable
  (default: `sqlite:///chessclub.db`)

### Schema

Six ORM models, each mapping 1:1 to a chessclub library dataclass:

```
clubs
  id (PK, slug)
  provider_id, name, description, country, url
  members_count, created_at, location, matches_count

members
  club_id (PK, FK → clubs.id)
  username (PK)
  rating, title, joined_at, activity

tournaments
  id (PK)
  name, tournament_type, status, start_date, end_date
  player_count, winner_username, winner_score
  club_slug (FK → clubs.id), url

tournament_results
  tournament_id (PK, FK → tournaments.id)
  player (PK)
  position, score, rating

games
  id (PK, auto-increment)
  white, black, result, opening_eco, pgn
  played_at, white_accuracy, black_accuracy
  tournament_id (FK → tournaments.id), url
  Indexes: ix_games_tournament, ix_games_players

club_records
  id (PK, auto-increment)
  club_id (FK → clubs.id)
  category, value, player, detail, date
```

### Population via Sync Worker

The persistence layer is **not populated by normal route usage**. Data
enters the database exclusively through the sync worker:

**Phase 1 (automatic, every N hours):**

| Step | Library Call | DB Function |
|------|-------------|-------------|
| Club overview | `ClubService.get_club()` | `upsert_club()` |
| Members | `ClubService.get_club_members()` | `upsert_members()` |
| Tournaments | `ClubService.get_club_tournaments()` | `upsert_tournaments()` |
| Results | `ClubService.get_tournament_results()` | `upsert_results()` |
| Leaderboard | `LeaderboardService.get_leaderboard()` | _(library cache only)_ |
| Attendance | `AttendanceService.get_attendance()` | _(library cache only)_ |

**Phase 2 (manual trigger, per-club):**

| Step | Library Call | DB Function |
|------|-------------|-------------|
| Game archives | `client.get_tournament_games()` | `upsert_games()` |
| Records | `RecordsService.get_records()` | `store_records()` |

### Write Strategies

| Function | Strategy | Rationale |
|----------|----------|-----------|
| `upsert_club()` | INSERT or UPDATE by PK | Club data evolves incrementally |
| `upsert_tournaments()` | INSERT or UPDATE by PK | New tournaments appear; existing ones change status |
| `upsert_results()` | INSERT or UPDATE by composite PK | Scores update as tournaments progress |
| `upsert_members()` | DELETE all + INSERT | Member list is a full snapshot; diff-based update would be complex |
| `upsert_games()` | DELETE all for tournament + INSERT | Games are a complete set per tournament |
| `store_records()` | DELETE all for club + INSERT | Records are recomputed in full |

### Computed Aggregates

Some read functions don't return stored rows directly but compute
aggregates from normalized data:

| Function | Computation |
|----------|-------------|
| `get_leaderboard()` | GROUP BY player across tournament results, optionally filtered by year/month |
| `get_matchups()` | GROUP BY (player_a, player_b) across games, ordered alphabetically |
| `get_attendance()` | Participation percentage + current/max streak from result presence |
| `get_rating_history()` | JOIN results with tournaments, ordered chronologically |

### Incremental Game Sync

`has_games(tournament_id)` checks if any game row exists for a tournament.
Phase 2 skips tournaments that already have games stored, only fetching
archives for newly finished tournaments. This minimizes HTTP requests to
Chess.com's API.

---

## How the Two Tiers Interact

The two caches are **independent**. Neither reads from nor writes to the
other. They serve different purposes:

| Aspect | Tier 1 (Library Cache) | Tier 2 (SQLAlchemy DB) |
|--------|----------------------|----------------------|
| **Purpose** | Reduce API calls during a session | Permanent data storage |
| **Populated by** | Any `ChessComClient` HTTP call | Sync worker only |
| **TTL** | 30 min – 30 days (per URL pattern) | Permanent (no expiry) |
| **Scope** | All API responses (any club) | Watched clubs only |
| **Survives cookie expiry** | No (entries expire, cannot re-fetch) | Yes (data persists forever) |
| **Used by routes** | Non-watched clubs (library fallback) | Watched clubs (DB-first path) |
| **Format** | Raw JSON HTTP response bodies | Normalized ORM rows |
| **Resilience** | Silent failure (graceful degradation) | Crashes propagate to the route |

### Data Flow for a Watched Club

```
1. Sync worker runs (every 6 hours):
   ChessComClient → Chess.com API → library cache (TTL)
                                   → db_service.upsert_*() → SQLAlchemy DB

2. User visits /club/<slug>/leaderboard:
   Route → db_service.get_club(slug)
         → found in DB → db_service.get_leaderboard(slug)
         → render template with DB data (library never called)
```

### Data Flow for a Non-Watched Club

```
1. User visits /club/<slug>/leaderboard:
   Route → db_service.get_club(slug)
         → NOT in DB → LeaderboardService(client).get_leaderboard()
                        → ChessComClient → library cache HIT? return cached
                                         → library cache MISS? Chess.com API
         → render template with live data
```

---

## Failure Modes and Recovery

| Scenario | Impact | Recovery |
|----------|--------|----------|
| Library cache file deleted | Next request hits Chess.com API; transparent to user | Automatic (cache rebuilt on demand) |
| Library cache corrupted | Silent failure; all requests go to API | Delete `~/.cache/chessclub/cache.db` |
| SQLAlchemy DB deleted | Watched clubs show empty data until next sync | Run sync from admin dashboard |
| Chess.com cookies expired | Library API calls fail with 401/403 | Update `ACCESS_TOKEN` and `PHPSESSID` in `.env` |
| Chess.com API rate limit | 429 responses (not cached, retryable) | Wait and retry; sync worker continues on next run |
| Chess.com API down | 5xx responses (not cached) | Data served from DB for watched clubs; non-watched clubs show error |

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URI` | `sqlite:///chessclub.db` | SQLAlchemy database URI |
| `SYNC_INTERVAL_HOURS` | `6` | Hours between automatic Phase 1 syncs |
| `WATCHED_CLUBS_FILE` | `watched_clubs.json` | Path to the JSON file listing club slugs to sync |

The library cache location (`~/.cache/chessclub/cache.db`) and TTL values
are configured in the chessclub library itself and cannot be overridden
from the web application.
