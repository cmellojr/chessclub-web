"""Flask application factory."""

import datetime

from flask import Flask

from config import Config


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---------- Database ----------
    from app.extensions import db

    db.init_app(app)
    with app.app_context():
        from app import models  # noqa: F401

        db.create_all()

    # ---------- Jinja2 filters ----------
    @app.template_filter("ts_to_date")
    def ts_to_date(ts):
        """Convert a Unix timestamp to a formatted date string."""
        if ts is None:
            return "—"
        try:
            return datetime.datetime.fromtimestamp(
                int(ts), tz=datetime.UTC
            ).strftime("%d/%m/%Y")
        except (ValueError, OSError):
            return "—"

    @app.template_filter("country_flag")
    def country_flag(country_url):
        """Extract a flag emoji + code from a Chess.com country URL.

        Example: "https://api.chess.com/pub/country/BR" → "🇧🇷 BR"
        """
        if not country_url or not isinstance(country_url, str):
            return country_url or "—"
        code = country_url.rstrip("/").split("/")[-1].upper()
        if len(code) != 2 or not code.isalpha():
            return country_url
        flag = "".join(
            chr(0x1F1E0 + ord(c) - ord("A")) for c in code
        )
        return f"{flag} {code}"

    @app.template_filter("ts_to_datetime")
    def ts_to_datetime(ts):
        """Convert a Unix timestamp to a formatted date-time string."""
        if ts is None:
            return "—"
        try:
            return datetime.datetime.fromtimestamp(
                int(ts), tz=datetime.UTC
            ).strftime("%d/%m/%Y %H:%M")
        except (ValueError, OSError):
            return "—"

    # ---------- Context processor ----------
    @app.context_processor
    def inject_auth_status():
        """Inject auth flags and sync status into all templates."""
        from app.sync import sync_status

        token = app.config.get("CHESSCOM_SERVER_ACCESS_TOKEN", "")
        sessid = app.config.get("CHESSCOM_SERVER_PHPSESSID", "")
        client_id = app.config.get("CHESSCOM_OAUTH_CLIENT_ID", "")
        return {
            "server_auth_configured": bool(token and sessid),
            "oauth_configured": bool(client_id),
            "sync_status": sync_status,
        }

    # ---------- Blueprints ----------
    from app.admin import admin_bp
    from app.auth import auth_bp
    from app.club import club_bp
    from app.player import player_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(club_bp)
    app.register_blueprint(player_bp)

    # ---------- Background sync scheduler ----------
    # Skip scheduler in the Flask reloader child process to avoid
    # running two schedulers simultaneously in debug mode.
    import os

    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from app.sync import init_scheduler

        init_scheduler(app)

    return app
