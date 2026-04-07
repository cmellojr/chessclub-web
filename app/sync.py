"""Background sync worker for pre-warming the chessclub cache.

Runs periodic jobs via APScheduler to fetch club data using server
cookies, populating both the chessclub library's built-in SQLite
cache and the application's SQLAlchemy database for permanent
persistence.

Two-phase sync:
  Phase 1 (automatic): overview, members, tournaments,
      tournament results, leaderboard, attendance.
  Phase 2 (manual trigger): game archives for each tournament,
      processed one-by-one. Once complete, matchups and records
      are computed from permanent DB storage.
"""

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from chessclub.providers.chesscom import (
    ChessComClient,
    ChessComCookieAuth,
)
from chessclub.services.attendance_service import AttendanceService
from chessclub.services.club_service import ClubService
from chessclub.services.leaderboard_service import (
    LeaderboardService,
)
from flask import Flask

log = logging.getLogger(__name__)

sync_status: dict = {
    "last_run": None,
    "running": False,
    "clubs": {},
}

_scheduler: BackgroundScheduler | None = None


def _default_game_sync() -> dict:
    """Return a fresh game_sync status dict."""
    return {
        "running": False,
        "total": 0,
        "done": 0,
        "current": None,
        "errors": [],
        "completed_at": None,
    }


def get_watched_clubs(path: str) -> list[str]:
    """Read the watched clubs list from a JSON file.

    Args:
        path: Path to the JSON file containing a list of
            club slugs.

    Returns:
        A list of club slug strings, or an empty list if the
        file is missing or invalid.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [s for s in data if isinstance(s, str) and s.strip()]
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return []


def save_watched_clubs(path: str, clubs: list[str]) -> None:
    """Write the watched clubs list to a JSON file.

    Args:
        path: Path to the JSON file.
        clubs: List of club slug strings.
    """
    Path(path).write_text(json.dumps(clubs, indent=2) + "\n", encoding="utf-8")


def _make_sync_client(app: Flask) -> ChessComClient | None:
    """Create a ChessComClient with server cookie credentials.

    Args:
        app: The Flask application instance.

    Returns:
        An authenticated client, or ``None`` if server
        credentials are not configured.
    """
    token = app.config.get("CHESSCOM_SERVER_ACCESS_TOKEN", "")
    sessid = app.config.get("CHESSCOM_SERVER_PHPSESSID", "")
    if not (token and sessid):
        return None
    auth = ChessComCookieAuth(access_token=token, phpsessid=sessid)
    return ChessComClient(user_agent=app.config["USER_AGENT"], auth=auth)


# ------------------------------------------------------------------
# Phase 1: Light data sync (automatic)
# ------------------------------------------------------------------


def sync_club(slug: str, client: ChessComClient) -> None:
    """Sync light data for a club (Phase 1).

    Fetches data via the chessclub library and persists it to the
    SQLAlchemy database. Updates ``sync_status`` in real time as
    each step completes. Preserves existing ``game_sync`` progress.

    Args:
        slug: The club slug to sync.
        client: An authenticated ChessComClient.
    """
    from app import db_service

    existing_game_sync = (
        sync_status["clubs"]
        .get(slug, {})
        .get("game_sync", _default_game_sync())
    )
    status = {
        "ok": True,
        "error": None,
        "synced_at": None,
        "steps": {},
        "game_sync": existing_game_sync,
    }
    sync_status["clubs"][slug] = status

    year = datetime.now(UTC).year
    club_svc = ClubService(client)

    # Each step returns its result so we can persist it to the DB.
    steps = [
        (
            "club_overview",
            lambda: club_svc.get_club(slug),
        ),
        (
            "members",
            lambda: club_svc.get_club_members(slug),
        ),
        (
            "tournaments",
            lambda: club_svc.get_club_tournaments(slug),
        ),
        (
            "leaderboard",
            lambda: LeaderboardService(client).get_leaderboard(slug, year=year),
        ),
        (
            "attendance",
            lambda: AttendanceService(client).get_attendance(slug, last_n=20),
        ),
    ]

    tournaments_data = None

    for name, fn in steps:
        try:
            result = fn()
            status["steps"][name] = "ok"
            log.info("Synced %s/%s", slug, name)

            # Persist to database
            if name == "club_overview" and result:
                db_service.upsert_club(result)
            elif name == "members" and result:
                db_service.upsert_members(slug, result)
            elif name == "tournaments" and result:
                db_service.upsert_tournaments(result)
                tournaments_data = result
        except Exception as exc:  # noqa: BLE001
            status["steps"][name] = str(exc)
            status["ok"] = False
            status["error"] = str(exc)
            log.warning("Sync failed %s/%s: %s", slug, name, exc)

    # Fetch and persist tournament results (per-tournament)
    if tournaments_data:
        try:
            for t in tournaments_data:
                results = club_svc.get_tournament_results(t)
                if results:
                    db_service.upsert_results(results)
            status["steps"]["tournament_results"] = "ok"
            log.info("Synced %s/tournament_results", slug)
        except Exception as exc:  # noqa: BLE001
            status["steps"]["tournament_results"] = str(exc)
            status["ok"] = False
            status["error"] = str(exc)
            log.warning("Sync failed %s/tournament_results: %s", slug, exc)

    status["synced_at"] = datetime.now(UTC)


def run_sync(app: Flask) -> None:
    """Run Phase 1 sync for all watched clubs.

    Args:
        app: The Flask application instance.
    """
    with app.app_context():
        clubs_file = app.config.get("WATCHED_CLUBS_FILE", "watched_clubs.json")
        clubs = get_watched_clubs(clubs_file)
        if not clubs:
            log.info("No watched clubs configured, skipping sync.")
            return

        client = _make_sync_client(app)
        if not client:
            log.warning("Server credentials not configured, skipping sync.")
            return

        sync_status["running"] = True
        log.info("Starting sync for %d club(s)...", len(clubs))
        for slug in clubs:
            sync_club(slug, client)
        sync_status["last_run"] = datetime.now(UTC)
        sync_status["running"] = False
        log.info("Sync complete.")


def trigger_sync_async(app: Flask) -> bool:
    """Trigger Phase 1 sync in a background thread.

    Args:
        app: The Flask application instance.

    Returns:
        ``True`` if started, ``False`` if already running.
    """
    if sync_status["running"]:
        return False
    thread = threading.Thread(target=run_sync, args=[app], daemon=True)
    thread.start()
    return True


# ------------------------------------------------------------------
# Phase 2: Game archive sync (manual, per-club)
# ------------------------------------------------------------------


def sync_club_games(slug: str, client: ChessComClient) -> None:
    """Sync game archives for all finished tournaments of a club.

    **Incremental:** skips tournaments that already have games
    stored in the database, and only processes finished ones.
    This minimizes HTTP requests to Chess.com.

    After new games are fetched, recomputes and stores club
    records.

    Args:
        slug: The club slug.
        client: An authenticated ChessComClient.
    """
    from chessclub.services.records_service import RecordsService

    from app import db_service

    all_tournaments = ClubService(client).get_club_tournaments(slug)
    all_tournaments.sort(key=lambda t: t.end_date or 0, reverse=True)

    # Only sync finished tournaments; skip those already in DB
    finished = [t for t in all_tournaments if t.status == "finished"]
    pending = [t for t in finished if not db_service.has_games(t.id)]
    skipped = len(finished) - len(pending)

    club_status = sync_status["clubs"].get(slug, {})
    game_sync = club_status.get("game_sync", _default_game_sync())
    club_status["game_sync"] = game_sync

    game_sync["running"] = True
    game_sync["total"] = len(pending)
    game_sync["done"] = 0
    game_sync["errors"] = []
    game_sync["completed_at"] = None

    if skipped:
        log.info(
            "Game sync %s: %d already in DB, %d to fetch.",
            slug,
            skipped,
            len(pending),
        )

    for t in pending:
        game_sync["current"] = t.name
        try:
            games = client.get_tournament_games(t)
            if games:
                db_service.upsert_games(t.id, games)
            log.info(
                "Game sync %s: %s (%d/%d)",
                slug,
                t.name,
                game_sync["done"] + 1,
                game_sync["total"],
            )
        except Exception as exc:  # noqa: BLE001
            game_sync["errors"].append(f"{t.name}: {exc}")
            log.warning(
                "Game sync failed %s/%s: %s",
                slug,
                t.name,
                exc,
            )
        game_sync["done"] += 1

    # Recompute records if new games were fetched
    if pending:
        try:
            records = RecordsService(client).get_records(slug)
            if records:
                db_service.store_records(slug, records)
            log.info("Stored records for %s.", slug)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Failed to compute records for %s: %s",
                slug,
                exc,
            )

    game_sync["running"] = False
    game_sync["current"] = None
    game_sync["completed_at"] = datetime.now(UTC)
    log.info("Game sync complete for %s.", slug)


def _run_game_sync(app: Flask, slug: str) -> None:
    """Run game sync inside an app context.

    Args:
        app: The Flask application instance.
        slug: The club slug to sync games for.
    """
    with app.app_context():
        client = _make_sync_client(app)
        if not client:
            log.warning("Server credentials not configured, cannot sync games.")
            return
        sync_club_games(slug, client)


def trigger_game_sync_async(app: Flask, slug: str) -> bool:
    """Trigger Phase 2 game sync in a background thread.

    Args:
        app: The Flask application instance.
        slug: The club slug.

    Returns:
        ``True`` if started, ``False`` if already running.
    """
    club_status = sync_status["clubs"].get(slug, {})
    game_sync = club_status.get("game_sync", {})
    if game_sync.get("running"):
        return False
    thread = threading.Thread(
        target=_run_game_sync,
        args=[app, slug],
        daemon=True,
    )
    thread.start()
    return True


# ------------------------------------------------------------------
# Scheduler
# ------------------------------------------------------------------


def init_scheduler(app: Flask) -> None:
    """Initialize APScheduler with the periodic sync job.

    Args:
        app: The Flask application instance.
    """
    global _scheduler  # noqa: PLW0603
    if _scheduler is not None:
        return

    interval = app.config.get("SYNC_INTERVAL_HOURS", 6)
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        run_sync,
        "interval",
        hours=interval,
        args=[app],
        id="club_sync",
        next_run_time=datetime.now(UTC),
    )
    _scheduler.start()
    log.info("Sync scheduler started (interval: %dh).", interval)
