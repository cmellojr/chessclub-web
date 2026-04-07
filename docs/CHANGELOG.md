# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-04-06

### Added

- SQLAlchemy persistence layer with 6 ORM models (`ClubModel`, `MemberModel`,
  `TournamentModel`, `TournamentResultModel`, `GameModel`, `ClubRecordModel`).
- Data access layer (`db_service.py`) with write functions for the sync worker
  and read functions that return library dataclass instances.
- Aggregate computations from DB: leaderboard, matchups, attendance, rating
  history, and club records.
- DB-first route pattern — watched clubs always served from the database,
  non-watched clubs fall back to the chessclub library.
- Incremental game sync — skips tournaments already stored in the database.
- Country flag emoji filter for club overview (parses Chess.com API country URL).
- Auto-refresh on admin dashboard while sync is running.
- Structured logging format with timestamps in `run.py`.
- `README.md` with badges, features, quick start, and architecture overview.
- `AGENTS.md` for AI coding agents (Jules, Codex, Copilot, Cursor).
- `CLAUDE.md` with project conventions and development commands.

### Changed

- Routes in `club.py` and `player.py` now query the database first instead of
  always calling the chessclub library.
- Enforced Google Python Style Guide across all Python files: type annotations,
  Google-convention docstrings, `X | Y` union syntax.
- Simplified exception handling — removed redundant `ChessclubError` catches
  where `Exception` already covers it.

### Fixed

- 403 Forbidden error on leaderboard and other authenticated pages for watched
  clubs when library cache expired.
- Club overview displaying raw Chess.com API URL instead of country name.
- HTML entities in club descriptions not rendering correctly in navigation.

## [0.2.0] - 2026-03-19

### Added

- Background sync worker using APScheduler for periodic data refresh.
- Admin dashboard at `/admin` with sync status, watched clubs management, and
  manual sync triggers.
- Two-phase sync architecture: Phase 1 (automatic) for light data, Phase 2
  (manual) for game archives.
- Game archive progress tracking with per-tournament status updates.
- `watched_clubs.json` configuration file for clubs to sync.
- `ADMIN_PASSWORD` and `SYNC_INTERVAL_HOURS` environment variables.

## [0.1.0] - 2026-03-18

### Added

- Flask web portal with club overview, members, tournaments, leaderboard,
  matchups, attendance, and records pages.
- Chess.com OAuth 2.0 PKCE authentication flow.
- Cookie-based server authentication fallback via `.env` credentials.
- Player rating history page with chart visualization.
- Bootstrap 5.3 responsive UI with Jinja2 templates.
- Club search on the index page.
- All user-facing text in English.

## [0.0.0] - 2026-02-27

### Added

- Initial repository setup with `.gitignore` and `LICENSE`.

[Unreleased]: https://github.com/cmellojr/chessclub-web/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/cmellojr/chessclub-web/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/cmellojr/chessclub-web/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/cmellojr/chessclub-web/compare/v0.0.0...v0.1.0
[0.0.0]: https://github.com/cmellojr/chessclub-web/releases/tag/v0.0.0
