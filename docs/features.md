# Feature Map

> Auto-maintained index of every user-facing feature and the code path that implements it. Updated alongside the code — not after the fact.

## Club Search

User enters a club slug on the homepage and is redirected to that club's overview page.

**Flow:**

1. `app/templates/index.html` — Search form with slug input, submits via GET to `/search`.
2. `app/club.py:search()` — Parses `?slug=` parameter; validates; redirects to `club.overview`.
3. `app/club.py:overview()` — Renders club overview page (see Club Overview feature).

---

## Club Overview

Displays club info: name, description, member count, team matches, country flag, founding date, slug, location, link.

**Flow:**

1. `app/club.py:overview()` — Route handler (`GET /club/<slug>`). DB-first: calls `db_service.get_club(slug)`. If found, renders with DB data. Falls back to `ClubService(client).get_club(slug)` via chessclub library.
2. `app/db_service.py:get_club()` — Queries `ClubModel` by slug PK, returns `Club` dataclass or `None`.
3. `app/chess_service.py:make_client()` — Creates authenticated `ChessComClient` for library fallback path.
4. `app/templates/club/overview.html` — Renders stat cards (members, matches, country flag, founded date) and detail table.
5. `app/templates/club/_nav.html` — Sub-navigation tabs for all club sections.

---

## Member List

Displays all club members with usernames, titles, ratings, activity status, and join dates.

**Flow:**

1. `app/club.py:members()` — Route handler (`GET /club/<slug>/members`). Accepts optional `?page=` and `?per_page=` params for pagination. DB-first: `db_service.get_members(slug, offset, limit)`. Falls back to `ClubService(client).get_club_members(slug)`.
2. `app/db_service.py:get_members()` — Queries `MemberModel` by club_id with offset/limit, returns `list[Member]` or `None`.
3. `app/db_service.py:count_members()` — Counts total members for pagination metadata.
4. `app/templates/club/members.html` — Table with member details; title badges, activity badges, Chess.com profile links.

---

## Tournament History

Lists all club tournaments with format, status, player count, winner, and dates.

**Flow:**

1. `app/club.py:tournaments()` — Route handler (`GET /club/<slug>/tournaments`). Accepts optional `?page=` and `?per_page=` params for pagination. DB-first: `db_service.get_tournaments(slug, offset, limit)`. Falls back to `ClubService(client).get_club_tournaments(slug)`. Requires auth for library path.
2. `app/db_service.py:get_tournaments()` — Queries `TournamentModel` by club_slug, ordered by end_date DESC with offset/limit, returns `list[Tournament]` or `None`.
3. `app/db_service.py:count_tournaments()` — Counts total tournaments for pagination metadata.
4. `app/templates/club/tournaments.html` — Table with format badges (Arena/Swiss), status badges, external Chess.com links.

---

## Leaderboard

Player rankings computed from tournament results, filterable by year and month.

**Flow:**

1. `app/club.py:leaderboard()` — Route handler (`GET /club/<slug>/leaderboard`). Accepts optional `?year=`, `?month=`, `?page=`, and `?per_page=` params. DB-first: `db_service.get_leaderboard(slug, year, month, offset, limit)`. Falls back to `LeaderboardService(client).get_leaderboard(slug, year, month)`.
2. `app/db_service.py:get_leaderboard()` — Computed aggregate: GROUP BY player across `TournamentResultModel` joined with `TournamentModel`, filtered by club_slug, status=finished, optional date range. Returns `(list[PlayerStats], total_count)` sorted by total_score DESC, with offset/limit pagination.
3. `app/templates/club/leaderboard.html` — Table with rank (medal emojis for top 3), player links, stats; filter form with year input and month dropdown.

---

## Matchups

Head-to-head win/draw/loss records between members, filterable by last N tournaments.

**Flow:**

1. `app/club.py:matchups()` — Route handler (`GET /club/<slug>/matchups`). Accepts `?last_n=` param. DB-first: `db_service.get_matchups(slug, last_n)`. Falls back to `MatchupService(client).get_matchups(slug, last_n)`.
2. `app/db_service.py:get_matchups()` — Computed aggregate: queries `GameModel` for club's finished tournaments, groups by alphabetical player pair, counts wins/draws/total. Returns `list[Matchup]` sorted by total_games DESC.
3. `app/templates/club/matchups.html` — Table with player A/B, wins, draws, total games, last played; filter form.

---

## Attendance

Tournament participation percentages and streak tracking (current and best streak).

**Flow:**

1. `app/club.py:attendance()` — Route handler (`GET /club/<slug>/attendance`). Accepts `?last_n=` param. DB-first: `db_service.get_attendance(slug, last_n)`. Falls back to `AttendanceService(client).get_attendance(slug, last_n)`.
2. `app/db_service.py:get_attendance()` — Computed aggregate: queries `TournamentResultModel` for club's finished tournaments, groups by player, computes participation percentage, current streak, max streak. Returns `list[AttendanceRecord]` sorted by participation_pct DESC.
3. `app/templates/club/attendance.html` — Table with progress bar, percentages, streak counts; filter form.

---

## Club Records

Notable club records displayed as cards (highest rating, best streak, etc.).

**Flow:**

1. `app/club.py:records()` — Route handler (`GET /club/<slug>/records`). Accepts `?last_n=` param. DB-first: `db_service.get_records(slug, last_n)`. Falls back to `RecordsService(client).get_records(slug, last_n)`.
2. `app/db_service.py:get_records()` — Queries `ClubRecordModel` by club_id, returns `list[ClubRecord]` or `None`.
3. `app/templates/club/records.html` — Card grid: category, value, player link, detail, date; filter form.

---

## Player Rating History

Player's rating evolution across club tournaments, with tournament name, format, rating, position, and score.

**Flow:**

1. `app/player.py:rating_history()` — Route handler (`GET /player/<username>/rating-history`). Requires `?club=` param, optional `?last_n=`. DB-first: `db_service.get_rating_history(slug, username, last_n)`. Falls back to `RatingHistoryService(client).get_rating_history(slug, username, last_n)`.
2. `app/db_service.py:get_rating_history()` — Computed aggregate: JOINs `TournamentResultModel` with `TournamentModel`, filtered by club_slug, status=finished, username (case-insensitive). Returns `list[RatingSnapshot]` sorted chronologically.
3. `app/templates/player/rating_history.html` — Table with date, tournament name, format badge, rating, position, score; start-to-final rating summary; back link.

---

## Background Sync (Phase 1)

Automatic periodic sync of club data (overview, members, tournaments, results, leaderboard, attendance) for all watched clubs.

**Flow:**

1. `app/sync.py:init_scheduler()` — Called from `app/__init__.py:create_app()`. Creates APScheduler `BackgroundScheduler` with interval job (`run_sync`) every `SYNC_INTERVAL_HOURS` (default: 6).
2. `app/sync.py:run_sync()` — Reads watched clubs from JSON, creates authenticated `ChessComClient`, iterates clubs calling `sync_club()`.
3. `app/sync.py:sync_club()` — For each step (club_overview, members, tournaments, leaderboard, attendance): calls chessclub library, persists via `db_service.upsert_*()`, updates `sync_status`. Tournament results fetched and persisted per-tournament.
4. `app/db_service.py:upsert_club()`, `upsert_members()`, `upsert_tournaments()`, `upsert_results()` — Write functions persisting library dataclasses to SQLAlchemy DB.
5. `app/sync.py:trigger_sync_async()` — Starts `run_sync` in a daemon thread; returns False if already running.
6. `app/admin.py:trigger_sync()` — Admin POST route (`POST /admin/sync`) calling `trigger_sync_async()`.

---

## Game Archive Sync (Phase 2)

Manual per-club sync of game archives for all finished tournaments, followed by records computation.

**Flow:**

1. `app/admin.py:trigger_game_sync()` — Admin POST route (`POST /admin/sync-games/<slug>`) calling `trigger_game_sync_async()`.
2. `app/sync.py:trigger_game_sync_async()` — Starts `_run_game_sync()` in a daemon thread; returns False if already running for this club.
3. `app/sync.py:sync_club_games()` — Fetches all club tournaments, filters finished ones, skips those already in DB (incremental via `db_service.has_games()`), fetches game archives, persists via `db_service.upsert_games()`. After all new games, computes records via `RecordsService` and persists via `db_service.store_records()`. Updates real-time `sync_status` progress.
4. `app/db_service.py:upsert_games()` — DELETE all games for tournament + INSERT batch.
5. `app/db_service.py:has_games()` — Checks if any game row exists for a tournament (incremental skip).
6. `app/db_service.py:store_records()` — DELETE all records for club + INSERT batch.
7. `app/templates/admin/dashboard.html` — Per-club game sync progress bar, status, errors.

---

## Admin Dashboard

Password-protected panel for managing watched clubs, triggering syncs, and monitoring progress.

**Flow:**

1. `app/admin.py:login()` — Route (`GET/POST /admin/login`): simple password form, sets `admin_authenticated` session flag. Disabled when `ADMIN_PASSWORD` is empty.
2. `app/admin.py:_require_admin()` — Decorator checking `admin_authenticated` and `ADMIN_PASSWORD` config.
3. `app/admin.py:dashboard()` — Route (`GET /admin/`): sync status overview, per-club step badges, game archive progress. Auto-refresh (5s meta tag) while any sync runs.
4. `app/admin.py:clubs()` — Route (`GET /admin/clubs`): watched clubs list with remove buttons.
5. `app/admin.py:add_club()` — Route (`POST /admin/clubs/add`): adds slug to watched clubs JSON.
6. `app/admin.py:remove_club()` — Route (`POST /admin/clubs/remove`): removes slug from JSON.
7. `app/sync.py:get_watched_clubs()` — Reads club slugs from JSON file.
8. `app/sync.py:save_watched_clubs()` — Writes club slugs to JSON file.
9. `app/sync.py:sync_status` — Module-level dict tracking sync progress; injected into all templates via context processor.
10. `app/templates/admin/dashboard.html` — Sync overview, per-club table, game archive row, error details.
11. `app/templates/admin/clubs.html` — Add club form, remove buttons per club.
12. `app/templates/admin/login.html` — Password form.

---

## OAuth Login (User)

Per-user Chess.com OAuth 2.0 PKCE authentication.

**Flow:**

1. `app/auth.py:login()` — Route (`GET /auth/login`): generates PKCE verifier + challenge, stores in session, redirects to Chess.com authorize URL.
2. `app/auth.py:callback()` — Route (`GET /auth/callback`): exchanges auth code for tokens, stores `oauth_token` and `chess_username` in session.
3. `app/auth.py:logout()` — Route (`GET /auth/logout`): clears OAuth credentials from session.
4. `app/chess_service.py:_SessionOAuthProvider` — AuthProvider wrapping session's `oauth_token` dict; 60-second expiry buffer.
5. `app/chess_service.py:make_client()` — Creates ChessComClient with OAuth Bearer, optionally layered on cookie auth.
6. `app/templates/base.html` — Navbar shows login/logout buttons based on OAuth state.

---

## Credential Setup Page

Instructions for configuring Chess.com server cookie credentials.

**Flow:**

1. `app/auth.py:setup()` — Route (`GET /auth/setup`): renders setup instructions template.
2. `app/templates/auth/setup.html` — Shows credential status, explains auth model, step-by-step guide for Cookie Helper extension and .env configuration.
3. `app/templates/base.html` — Navbar status indicator linking to setup page.
4. `app/__init__.py:inject_auth_status()` — Context processor provides `server_auth_configured` and `oauth_configured` to all templates.

---

## Sync Status Indicator

Navbar shows authentication status and last sync timestamp.

**Flow:**

1. `app/__init__.py:inject_auth_status()` — Context processor injects `sync_status` and `server_auth_configured` into all templates.
2. `app/sync.py:sync_status` — Dict with `last_run`, `running`, `clubs` sub-dicts, updated by `run_sync()` and `sync_club_games()`.
3. `app/templates/base.html` — Navbar shows sync timestamp tooltip, server auth badge.
4. `app/templates/index.html` — Warning banner redirecting to setup when unauthenticated.

---

## Authentication Barrier

Auth-required club sections locked for unauthenticated users.

**Flow:**

1. `app/club.py:_require_auth()` — Helper checking `chess_service.is_authenticated()`, redirects to setup with flash if not.
2. `app/club.py:_handle_auth_error()` — Helper redirecting to setup with expired-credentials flash.
3. `app/club.py:tournaments()`, `leaderboard()`, `matchups()`, `attendance()`, `records()` — Call `_require_auth()` before library path; catch `AuthenticationRequiredError`.
4. `app/templates/club/_nav.html` — Lock icons on auth-required tabs for unauthenticated users; links to login with `next` redirect.
