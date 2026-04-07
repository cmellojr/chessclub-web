"""Blueprint for player-related pages."""

from chessclub.core.exceptions import (
    AuthenticationRequiredError,
    ChessclubError,
)
from chessclub.services.rating_history_service import RatingHistoryService
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app import chess_service, db_service

player_bp = Blueprint("player", __name__, url_prefix="/player")


@player_bp.route("/<username>/rating-history")
def rating_history(username: str):
    """Display a player's rating evolution across club tournaments.

    Accepts optional ``club`` and ``last_n`` query parameters.

    Args:
        username: The Chess.com username.
    """
    slug = request.args.get("club", "").strip()
    last_n = request.args.get("last_n", default=None, type=int)

    if not slug:
        flash("Provide the club slug via ?club= parameter.", "warning")
        return redirect(url_for("club.index"))

    # Try database first — for watched clubs, always use DB
    club = db_service.get_club(slug)
    if club:
        snapshots = db_service.get_rating_history(slug, username, last_n=last_n)
        return render_template(
            "player/rating_history.html",
            username=username,
            slug=slug,
            snapshots=snapshots or [],
            last_n=last_n,
            authenticated=chess_service.is_authenticated(session),
        )

    # Non-watched club — fall back to library (requires auth)
    if not chess_service.is_authenticated(session):
        flash(
            "This page requires Chess.com "
            "credentials configured on the server.",
            "warning",
        )
        return redirect(url_for("auth.setup"))

    try:
        client = chess_service.make_client(session)
        snapshots = RatingHistoryService(client).get_rating_history(
            slug, username, last_n=last_n
        )
    except AuthenticationRequiredError:
        flash(
            "Credentials expired or invalid. Please reconfigure .env.",
            "danger",
        )
        return redirect(url_for("auth.setup"))
    except (ChessclubError, Exception) as exc:
        flash(str(exc), "danger")
        return redirect(url_for("club.index"))

    return render_template(
        "player/rating_history.html",
        username=username,
        slug=slug,
        snapshots=snapshots,
        last_n=last_n,
        authenticated=True,
    )
