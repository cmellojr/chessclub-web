"""Flask application factory."""

import datetime

from flask import Flask

from config import Config


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

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
        """Inject auth flags into all templates."""
        token = app.config.get("CHESSCOM_SERVER_ACCESS_TOKEN", "")
        sessid = app.config.get("CHESSCOM_SERVER_PHPSESSID", "")
        client_id = app.config.get("CHESSCOM_OAUTH_CLIENT_ID", "")
        return {
            "server_auth_configured": bool(token and sessid),
            "oauth_configured": bool(client_id),
        }

    # ---------- Blueprints ----------
    from app.auth import auth_bp
    from app.club import club_bp
    from app.player import player_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(club_bp)
    app.register_blueprint(player_bp)

    return app
