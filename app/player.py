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

    # Try database first
    snapshots = db_service.get_rating_history(slug, username, last_n=last_n)
    if snapshots is not None:
        return render_template(
            "player/rating_history.html",
            username=username,
            slug=slug,
            snapshots=snapshots,
            last_n=last_n,
            authenticated=chess_service.is_authenticated(session),
        )

    # Fall back to library (requires auth)
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
    except ChessclubError as exc:
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
