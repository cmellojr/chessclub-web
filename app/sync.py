"""Background sync worker for pre-warming the chessclub cache.

Runs periodic jobs via APScheduler to fetch club data using server
cookies, populating the chessclub library's built-in SQLite cache so
that visitors always get fast, cached responses.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from chessclub.providers.chesscom import ChessComClient, ChessComCookieAuth
from chessclub.services.attendance_service import AttendanceService
from chessclub.services.club_service import ClubService
from chessclub.services.leaderboard_service import LeaderboardService
from chessclub.services.matchup_service import MatchupService
from chessclub.services.records_service import RecordsService

log = logging.getLogger(__name__)

sync_status: dict = {"last_run": None, "clubs": {}}

_scheduler: BackgroundScheduler | None = None


def get_watched_clubs(path: str) -> list[str]:
    """Read the watched clubs list from a JSON file.

    Args:
        path: Path to the JSON file containing a list of club slugs.

    Returns:
        A list of club slug strings, or an empty list if the file
        is missing or invalid.
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
        An authenticated client, or ``None`` if server credentials
        are not configured.
    """
    token = app.config.get("CHESSCOM_SERVER_ACCESS_TOKEN", "")
    sessid = app.config.get("CHESSCOM_SERVER_PHPSESSID", "")
    if not (token and sessid):
        return None
    auth = ChessComCookieAuth(access_token=token, phpsessid=sessid)
    return ChessComClient(user_agent=app.config["USER_AGENT"], auth=auth)


def sync_club(slug: str, client: ChessComClient) -> dict:
    """Sync all data for a single club, populating the cache.

    Args:
        slug: The club slug to sync.
        client: An authenticated ChessComClient.

    Returns:
        A dict with sync result details for this club.
    """
    result = {
        "ok": True,
        "error": None,
        "synced_at": datetime.now(UTC),
        "steps": {},
    }
    steps = [
        ("club_overview", lambda: ClubService(client).get_club(slug)),
        ("members", lambda: ClubService(client).get_club_members(slug)),
        (
            "tournaments",
            lambda: ClubService(client).get_club_tournaments(slug),
        ),
        (
            "leaderboard",
            lambda: LeaderboardService(client).get_leaderboard(slug),
        ),
        (
            "attendance",
            lambda: AttendanceService(client).get_attendance(slug),
        ),
        (
            "matchups",
            lambda: MatchupService(client).get_matchups(slug),
        ),
        (
            "records",
            lambda: RecordsService(client).get_records(slug),
        ),
    ]
    for name, fn in steps:
        try:
            fn()
            result["steps"][name] = "ok"
            log.info("Synced %s/%s", slug, name)
        except Exception as exc:  # noqa: BLE001
            result["steps"][name] = str(exc)
            result["ok"] = False
            result["error"] = str(exc)
            log.warning("Sync failed %s/%s: %s", slug, name, exc)
    return result


def run_sync(app) -> None:
    """Run sync for all watched clubs.

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

        log.info("Starting sync for %d club(s)...", len(clubs))
        for slug in clubs:
            sync_status["clubs"][slug] = sync_club(slug, client)
        sync_status["last_run"] = datetime.now(UTC)
        log.info("Sync complete.")


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
