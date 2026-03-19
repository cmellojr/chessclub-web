"""Blueprint for club-related pages."""

from chessclub.core.exceptions import (
    AuthenticationRequiredError,
    ChessclubError,
)
from chessclub.services.attendance_service import AttendanceService
from chessclub.services.club_service import ClubService
from chessclub.services.leaderboard_service import LeaderboardService
from chessclub.services.matchup_service import MatchupService
from chessclub.services.records_service import RecordsService
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app import chess_service

club_bp = Blueprint("club", __name__)


def _require_auth():
    """Redirect to setup if unauthenticated.

    Returns:
        A redirect response if not authenticated,
        or ``None`` otherwise.
    """
    if not chess_service.is_authenticated(session):
        flash(
            "This section requires Chess.com "
            "credentials configured on the server.",
            "warning",
        )
        return redirect(url_for("auth.setup"))
    return None


def _handle_auth_error():
    """Redirect to setup after an auth error."""
    flash(
        "Chess.com credentials invalid or expired. Please reconfigure .env.",
        "danger",
    )
    return redirect(url_for("auth.setup"))


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------


@club_bp.route("/")
def index():
    """Render the homepage with a club search form."""
    return render_template("index.html")


@club_bp.route("/search")
def search():
    """Redirect to the club overview based on the submitted slug.

    Accepts a GET form with a ``slug`` field.
    """
    slug = request.args.get("slug", "").strip()
    if not slug:
        flash("Enter the club identifier (slug).", "warning")
        return redirect(url_for("club.index"))
    return redirect(url_for("club.overview", slug=slug))


# ---------------------------------------------------------------------------
# Club pages
# ---------------------------------------------------------------------------


@club_bp.route("/club/<slug>")
def overview(slug: str):
    """Display general information about a club.

    Args:
        slug: The URL-friendly club identifier.
    """
    try:
        client = chess_service.make_client(session)
        svc = ClubService(client)
        club = svc.get_club(slug)
    except ChessclubError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.index"))
    return render_template(
        "club/overview.html",
        club=club,
        slug=slug,
        authenticated=chess_service.is_authenticated(session),
    )


@club_bp.route("/club/<slug>/members")
def members(slug: str):
    """Display the member list of a club.

    Args:
        slug: The URL-friendly club identifier.
    """
    try:
        client = chess_service.make_client(session)
        svc = ClubService(client)
        club = svc.get_club(slug)
        members_list = svc.get_club_members(slug)
    except ChessclubError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.overview", slug=slug))
    return render_template(
        "club/members.html",
        club=club,
        slug=slug,
        members=members_list,
        authenticated=chess_service.is_authenticated(session),
    )


@club_bp.route("/club/<slug>/tournaments")
def tournaments(slug: str):
    """Display tournaments organized by a club.

    Requires authentication.

    Args:
        slug: The URL-friendly club identifier.
    """
    redir = _require_auth()
    if redir:
        return redir
    try:
        client = chess_service.make_client(session)
        svc = ClubService(client)
        club = svc.get_club(slug)
        tournaments_list = svc.get_club_tournaments(slug)
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except ChessclubError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.overview", slug=slug))
    return render_template(
        "club/tournaments.html",
        club=club,
        slug=slug,
        tournaments=tournaments_list,
        authenticated=True,
    )


@club_bp.route("/club/<slug>/leaderboard")
def leaderboard(slug: str):
    """Display the tournament leaderboard for a club.

    Requires authentication. Accepts optional ``year`` and ``month`` query
    parameters for filtering.

    Args:
        slug: The URL-friendly club identifier.
    """
    redir = _require_auth()
    if redir:
        return redir

    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    try:
        client = chess_service.make_client(session)
        club = ClubService(client).get_club(slug)
        stats = LeaderboardService(client).get_leaderboard(
            slug, year=year, month=month
        )
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except ChessclubError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.overview", slug=slug))
    return render_template(
        "club/leaderboard.html",
        club=club,
        slug=slug,
        stats=stats,
        year=year,
        month=month,
        authenticated=True,
    )


@club_bp.route("/club/<slug>/matchups")
def matchups(slug: str):
    """Display head-to-head records between club members.

    Requires authentication. Accepts an optional ``last_n`` query parameter.

    Args:
        slug: The URL-friendly club identifier.
    """
    redir = _require_auth()
    if redir:
        return redir

    last_n = request.args.get("last_n", default=5, type=int) or None

    try:
        client = chess_service.make_client(session)
        club = ClubService(client).get_club(slug)
        matchups_list = MatchupService(client).get_matchups(slug, last_n=last_n)
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except ChessclubError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.overview", slug=slug))
    return render_template(
        "club/matchups.html",
        club=club,
        slug=slug,
        matchups=matchups_list,
        last_n=last_n,
        authenticated=True,
    )


@club_bp.route("/club/<slug>/attendance")
def attendance(slug: str):
    """Display tournament attendance statistics for club members.

    Requires authentication. Accepts an optional ``last_n`` query parameter.

    Args:
        slug: The URL-friendly club identifier.
    """
    redir = _require_auth()
    if redir:
        return redir

    last_n = request.args.get("last_n", default=None, type=int)

    try:
        client = chess_service.make_client(session)
        club = ClubService(client).get_club(slug)
        records = AttendanceService(client).get_attendance(slug, last_n=last_n)
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except ChessclubError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.overview", slug=slug))
    return render_template(
        "club/attendance.html",
        club=club,
        slug=slug,
        records=records,
        last_n=last_n,
        authenticated=True,
    )


@club_bp.route("/club/<slug>/records")
def records(slug: str):
    """Display notable records and highlights for a club.

    Requires authentication. Accepts an optional ``last_n`` query parameter
    controlling how many recent tournaments are scanned for game-based records.

    Args:
        slug: The URL-friendly club identifier.
    """
    redir = _require_auth()
    if redir:
        return redir

    last_n = request.args.get("last_n", default=5, type=int)

    try:
        client = chess_service.make_client(session)
        club = ClubService(client).get_club(slug)
        club_records = RecordsService(client).get_records(slug, last_n=last_n)
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except ChessclubError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.overview", slug=slug))
    return render_template(
        "club/records.html",
        club=club,
        slug=slug,
        records=club_records,
        last_n=last_n,
        authenticated=True,
    )
