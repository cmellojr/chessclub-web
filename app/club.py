"""Blueprint for club-related pages."""

import math
from urllib.parse import urlencode

import requests
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
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app import chess_service, db_service

club_bp = Blueprint("club", __name__)


def _require_auth() -> Response | None:
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


def _handle_auth_error() -> Response:
    """Redirect to setup after an auth error.

    Returns:
        A redirect response to the auth setup page.
    """
    flash(
        "Chess.com credentials invalid or expired. Please reconfigure .env.",
        "danger",
    )
    return redirect(url_for("auth.setup"))


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------


@club_bp.route("/")
def index() -> str:
    """Render the homepage with a club search form.

    Returns:
        The rendered homepage template.
    """
    return render_template("index.html")


@club_bp.route("/search")
def search() -> Response:
    """Redirect to the club overview based on the submitted slug.

    Accepts a GET form with a ``slug`` field.

    Returns:
        A redirect to the club overview or back to the homepage.
    """
    slug = request.args.get("slug", "").strip()
    if not slug:
        flash("Enter the club identifier (slug).", "warning")
        return redirect(url_for("club.index"))
    return redirect(url_for("club.overview", slug=slug))


# ---------------------------------------------------------------------------
# Club pages (DB first, library fallback)
# ---------------------------------------------------------------------------


@club_bp.route("/club/<slug>")
def overview(slug: str) -> str | Response:
    """Display general information about a club.

    Args:
        slug: The URL-friendly club identifier.

    Returns:
        The rendered overview template, or a redirect on error.
    """
    club = db_service.get_club(slug)
    if club:
        return render_template(
            "club/overview.html",
            club=club,
            slug=slug,
            authenticated=chess_service.is_authenticated(session),
        )

    try:
        client = chess_service.make_client(session)
        club = ClubService(client).get_club(slug)
    except (ChessclubError, requests.RequestException) as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.index"))
    return render_template(
        "club/overview.html",
        club=club,
        slug=slug,
        authenticated=chess_service.is_authenticated(session),
    )


@club_bp.route("/club/<slug>/members")
def members(slug: str) -> str | Response:
    """Display the member list of a club.

    Accepts optional ``page`` and ``per_page`` query parameters
    for pagination.

    Args:
        slug: The URL-friendly club identifier.

    Returns:
        The rendered members template, or a redirect on error.
    """
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    per_page = request.args.get("per_page", type=int)
    if per_page is not None and per_page < 1:
        per_page = None
    offset = (page - 1) * per_page if per_page is not None else None

    club = db_service.get_club(slug)
    if club:
        total = db_service.count_members(slug)
        total_pages = max(math.ceil(total / per_page), 1) if per_page else 1
        if page > total_pages:
            page = total_pages
            offset = (page - 1) * per_page if per_page is not None else None
        members_list = db_service.get_members(
            slug, offset=offset, limit=per_page,
        )
        return render_template(
            "club/members.html",
            club=club,
            slug=slug,
            members=members_list or [],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            authenticated=chess_service.is_authenticated(session),
        )

    redir = _require_auth()
    if redir:
        return redir
    try:
        client = chess_service.make_client(session)
        svc = ClubService(client)
        club = svc.get_club(slug)
        members_list = svc.get_club_members(slug)
        total = len(members_list) if members_list else 0
        if offset is not None and per_page is not None:
            members_list = (members_list or [])[offset : offset + per_page]
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except (ChessclubError, requests.RequestException) as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.overview", slug=slug))
    total_pages = max(math.ceil(total / per_page), 1) if per_page else 1
    return render_template(
        "club/members.html",
        club=club,
        slug=slug,
        members=members_list,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        authenticated=True,
    )


@club_bp.route("/club/<slug>/tournaments")
def tournaments(slug: str) -> str | Response:
    """Display tournaments organized by a club.

    Accepts optional ``page`` and ``per_page`` query parameters
    for pagination.

    Args:
        slug: The URL-friendly club identifier.

    Returns:
        The rendered tournaments template, or a redirect on error.
    """
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    per_page = request.args.get("per_page", type=int)
    if per_page is not None and per_page < 1:
        per_page = None
    offset = (page - 1) * per_page if per_page is not None else None

    club = db_service.get_club(slug)
    if club:
        total = db_service.count_tournaments(slug)
        total_pages = max(math.ceil(total / per_page), 1) if per_page else 1
        if page > total_pages:
            page = total_pages
            offset = (page - 1) * per_page if per_page is not None else None
        tournaments_list = db_service.get_tournaments(
            slug, offset=offset, limit=per_page,
        )
        return render_template(
            "club/tournaments.html",
            club=club,
            slug=slug,
            tournaments=tournaments_list or [],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            authenticated=chess_service.is_authenticated(session),
        )

    redir = _require_auth()
    if redir:
        return redir
    try:
        client = chess_service.make_client(session)
        svc = ClubService(client)
        club = svc.get_club(slug)
        tournaments_list = svc.get_club_tournaments(slug)
        total = len(tournaments_list) if tournaments_list else 0
        if offset is not None and per_page is not None:
            tournaments_list = (tournaments_list or [])[
                offset : offset + per_page
            ]
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except (ChessclubError, requests.RequestException) as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.overview", slug=slug))
    total_pages = max(math.ceil(total / per_page), 1) if per_page else 1
    return render_template(
        "club/tournaments.html",
        club=club,
        slug=slug,
        tournaments=tournaments_list,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        authenticated=True,
    )


@club_bp.route("/club/<slug>/leaderboard")
def leaderboard(slug: str) -> str | Response:
    """Display the tournament leaderboard for a club.

    Accepts optional ``year``, ``month``, ``page``, and ``per_page``
    query parameters.

    Args:
        slug: The URL-friendly club identifier.

    Returns:
        The rendered leaderboard template, or a redirect on error.
    """
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    per_page = request.args.get("per_page", type=int)
    if per_page is not None and per_page < 1:
        per_page = None
    offset = (page - 1) * per_page if per_page is not None else None

    club = db_service.get_club(slug)
    if club:
        stats, total = db_service.get_leaderboard(
            slug, year=year, month=month, offset=offset, limit=per_page,
        )
        skip = {"page", "per_page"}
        clean_args = [(k, v) for k, v in request.args.items() if k not in skip]
        pagination_qs = urlencode(clean_args)
        total_pages = max(math.ceil(total / per_page), 1) if per_page else 1
        return render_template(
            "club/leaderboard.html",
            club=club,
            slug=slug,
            stats=stats or [],
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            pagination_qs=pagination_qs,
            year=year,
            month=month,
            authenticated=chess_service.is_authenticated(session),
        )

    redir = _require_auth()
    if redir:
        return redir
    try:
        client = chess_service.make_client(session)
        club = ClubService(client).get_club(slug)
        all_stats = LeaderboardService(client).get_leaderboard(
            slug, year=year, month=month
        )
        total = len(all_stats) if all_stats else 0
        if offset is not None and per_page is not None:
            stats = (all_stats or [])[offset : offset + per_page]
        else:
            stats = all_stats or []
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except (ChessclubError, requests.RequestException) as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.overview", slug=slug))
    skip = {"page", "per_page"}
    clean_args = [(k, v) for k, v in request.args.items() if k not in skip]
    pagination_qs = urlencode(clean_args)
    total_pages = max(math.ceil(total / per_page), 1) if per_page else 1
    return render_template(
        "club/leaderboard.html",
        club=club,
        slug=slug,
        stats=stats,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        pagination_qs=pagination_qs,
        year=year,
        month=month,
        authenticated=True,
    )


@club_bp.route("/club/<slug>/matchups")
def matchups(slug: str) -> str | Response:
    """Display head-to-head records between club members.

    Accepts an optional ``last_n`` query parameter.

    Args:
        slug: The URL-friendly club identifier.

    Returns:
        The rendered matchups template, or a redirect on error.
    """
    last_n = request.args.get("last_n", default=5, type=int) or None

    club = db_service.get_club(slug)
    if club:
        matchups_list = db_service.get_matchups(slug, last_n=last_n)
        return render_template(
            "club/matchups.html",
            club=club,
            slug=slug,
            matchups=matchups_list or [],
            last_n=last_n,
            authenticated=chess_service.is_authenticated(session),
        )

    redir = _require_auth()
    if redir:
        return redir
    try:
        client = chess_service.make_client(session)
        club = ClubService(client).get_club(slug)
        matchups_list = MatchupService(client).get_matchups(slug, last_n=last_n)
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except (ChessclubError, requests.RequestException) as exc:
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
def attendance(slug: str) -> str | Response:
    """Display tournament attendance statistics for club members.

    Accepts an optional ``last_n`` query parameter.

    Args:
        slug: The URL-friendly club identifier.

    Returns:
        The rendered attendance template, or a redirect on error.
    """
    last_n = request.args.get("last_n", default=None, type=int)

    club = db_service.get_club(slug)
    if club:
        att_records = db_service.get_attendance(slug, last_n=last_n)
        return render_template(
            "club/attendance.html",
            club=club,
            slug=slug,
            records=att_records or [],
            last_n=last_n,
            authenticated=chess_service.is_authenticated(session),
        )

    redir = _require_auth()
    if redir:
        return redir
    try:
        client = chess_service.make_client(session)
        club = ClubService(client).get_club(slug)
        att_records = AttendanceService(client).get_attendance(
            slug, last_n=last_n
        )
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except (ChessclubError, requests.RequestException) as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.overview", slug=slug))
    return render_template(
        "club/attendance.html",
        club=club,
        slug=slug,
        records=att_records,
        last_n=last_n,
        authenticated=True,
    )


@club_bp.route("/club/<slug>/records")
def records(slug: str) -> str | Response:
    """Display notable records and highlights for a club.

    Accepts an optional ``last_n`` query parameter.

    Args:
        slug: The URL-friendly club identifier.

    Returns:
        The rendered records template, or a redirect on error.
    """
    last_n = request.args.get("last_n", default=5, type=int)

    club = db_service.get_club(slug)
    if club:
        club_records = db_service.get_records(slug, last_n=last_n)
        return render_template(
            "club/records.html",
            club=club,
            slug=slug,
            records=club_records or [],
            last_n=last_n,
            authenticated=chess_service.is_authenticated(session),
        )

    redir = _require_auth()
    if redir:
        return redir
    try:
        client = chess_service.make_client(session)
        club = ClubService(client).get_club(slug)
        club_records = RecordsService(client).get_records(slug, last_n=last_n)
    except AuthenticationRequiredError:
        return _handle_auth_error()
    except (ChessclubError, requests.RequestException) as exc:
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
