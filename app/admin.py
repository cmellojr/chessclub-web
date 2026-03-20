"""Admin blueprint for managing the background sync worker."""

from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.sync import (
    get_watched_clubs,
    save_watched_clubs,
    sync_status,
    trigger_game_sync_async,
    trigger_sync_async,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _require_admin(f):
    """Decorator that restricts access to admin-authenticated users.

    Args:
        f: The view function to wrap.

    Returns:
        The wrapped view function.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        password = current_app.config.get("ADMIN_PASSWORD", "")
        if not password:
            flash(
                "Admin access is disabled. Set ADMIN_PASSWORD in .env.",
                "danger",
            )
            return redirect(url_for("club.index"))
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)

    return decorated


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin login page with simple password authentication."""
    password = current_app.config.get("ADMIN_PASSWORD", "")
    if not password:
        flash(
            "Admin access is disabled. Set ADMIN_PASSWORD in .env.",
            "danger",
        )
        return redirect(url_for("club.index"))

    if request.method == "POST":
        if request.form.get("password") == password:
            session["admin_authenticated"] = True
            return redirect(url_for("admin.dashboard"))
        flash("Incorrect password.", "danger")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    """Log out of the admin panel."""
    session.pop("admin_authenticated", None)
    flash("Logged out of admin panel.", "info")
    return redirect(url_for("club.index"))


@admin_bp.route("/")
@_require_admin
def dashboard():
    """Admin dashboard showing sync status per club."""
    clubs_file = current_app.config.get(
        "WATCHED_CLUBS_FILE", "watched_clubs.json"
    )
    clubs = get_watched_clubs(clubs_file)
    return render_template(
        "admin/dashboard.html",
        sync_status=sync_status,
        watched_clubs=clubs,
    )


@admin_bp.route("/clubs")
@_require_admin
def clubs():
    """Manage the list of watched clubs."""
    clubs_file = current_app.config.get(
        "WATCHED_CLUBS_FILE", "watched_clubs.json"
    )
    club_list = get_watched_clubs(clubs_file)
    return render_template(
        "admin/clubs.html",
        watched_clubs=club_list,
    )


@admin_bp.route("/clubs/add", methods=["POST"])
@_require_admin
def add_club():
    """Add a club slug to the watched list."""
    slug = request.form.get("slug", "").strip().lower()
    if not slug:
        flash("Please enter a club slug.", "warning")
        return redirect(url_for("admin.clubs"))

    clubs_file = current_app.config.get(
        "WATCHED_CLUBS_FILE", "watched_clubs.json"
    )
    club_list = get_watched_clubs(clubs_file)
    if slug in club_list:
        flash(f"Club '{slug}' is already in the list.", "info")
    else:
        club_list.append(slug)
        save_watched_clubs(clubs_file, club_list)
        flash(f"Added '{slug}' to watched clubs.", "success")
    return redirect(url_for("admin.clubs"))


@admin_bp.route("/clubs/remove", methods=["POST"])
@_require_admin
def remove_club():
    """Remove a club slug from the watched list."""
    slug = request.form.get("slug", "").strip().lower()
    clubs_file = current_app.config.get(
        "WATCHED_CLUBS_FILE", "watched_clubs.json"
    )
    club_list = get_watched_clubs(clubs_file)
    if slug in club_list:
        club_list.remove(slug)
        save_watched_clubs(clubs_file, club_list)
        flash(f"Removed '{slug}' from watched clubs.", "success")
    else:
        flash(f"Club '{slug}' not found in the list.", "warning")
    return redirect(url_for("admin.clubs"))


@admin_bp.route("/sync", methods=["POST"])
@_require_admin
def trigger_sync():
    """Trigger a Phase 1 sync run in the background."""
    started = trigger_sync_async(current_app._get_current_object())
    if started:
        flash("Sync started in background.", "info")
    else:
        flash("A sync is already running.", "warning")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/sync-games/<slug>", methods=["POST"])
@_require_admin
def trigger_game_sync(slug: str):
    """Trigger Phase 2 game archive sync for a specific club.

    Args:
        slug: The club slug to sync games for.
    """
    started = trigger_game_sync_async(current_app._get_current_object(), slug)
    if started:
        flash(
            f"Game sync started for '{slug}'. Refresh to see progress.",
            "info",
        )
    else:
        flash(
            f"Game sync for '{slug}' is already running.",
            "warning",
        )
    return redirect(url_for("admin.dashboard"))
