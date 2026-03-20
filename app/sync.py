"""Background sync worker for pre-warming the chessclub cache.

Runs periodic jobs via APScheduler to fetch club data using server
cookies, populating the chessclub library's built-in SQLite cache so
that visitors always get fast, cached responses.

Two-phase sync:
  Phase 1 (automatic, ~15s): overview, members, tournaments,
      leaderboard, attendance.
  Phase 2 (manual trigger): game archives for each tournament,
      processed one-by-one. Once complete, matchups and records
      pages read from warm cache in <2 seconds.
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


def _make_sync_client(app) -> ChessComClient | None:
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

    Updates ``sync_status`` in real time as each step completes.
    Preserves existing ``game_sync`` progress if present.

    Args:
        slug: The club slug to sync.
        client: An authenticated ChessComClient.
    """
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
    steps = [
        (
            "club_overview",
            lambda: ClubService(client).get_club(slug),
        ),
        (
            "members",
            lambda: ClubService(client).get_club_members(slug),
        ),
        (
            "tournaments",
            lambda: ClubService(client).get_club_tournaments(slug),
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
    for name, fn in steps:
        try:
            fn()
            status["steps"][name] = "ok"
            log.info("Synced %s/%s", slug, name)
        except Exception as exc:  # noqa: BLE001
            status["steps"][name] = str(exc)
            status["ok"] = False
            status["error"] = str(exc)
            log.warning("Sync failed %s/%s: %s", slug, name, exc)
    status["synced_at"] = datetime.now(UTC)


def run_sync(app) -> None:
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


def trigger_sync_async(app) -> bool:
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
    """Pre-warm game archives for all tournaments of a club.

    Processes tournaments one by one (newest first), calling
    ``client.get_tournament_games()`` for each. This populates
    the SQLite cache so that matchups and records pages load
    instantly afterward.

    Args:
        slug: The club slug.
        client: An authenticated ChessComClient.
    """
    tournaments = ClubService(client).get_club_tournaments(slug)
    tournaments.sort(key=lambda t: t.end_date or 0, reverse=True)

    club_status = sync_status["clubs"].get(slug, {})
    game_sync = club_status.get("game_sync", _default_game_sync())
    club_status["game_sync"] = game_sync

    game_sync["running"] = True
    game_sync["total"] = len(tournaments)
    game_sync["done"] = 0
    game_sync["errors"] = []
    game_sync["completed_at"] = None

    for t in tournaments:
        game_sync["current"] = t.name
        try:
            client.get_tournament_games(t)
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

    game_sync["running"] = False
    game_sync["current"] = None
    game_sync["completed_at"] = datetime.now(UTC)
    log.info("Game sync complete for %s.", slug)


def _run_game_sync(app, slug: str) -> None:
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


def trigger_game_sync_async(app, slug: str) -> bool:
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


def init_scheduler(app) -> None:
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
