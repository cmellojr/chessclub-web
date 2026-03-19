"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    # Chess.com OAuth PKCE (register your app at Chess.com Developer Community)
    CHESSCOM_OAUTH_CLIENT_ID = os.environ.get("CHESSCOM_OAUTH_CLIENT_ID", "")
    OAUTH_REDIRECT_URI = os.environ.get(
        "OAUTH_REDIRECT_URI", "http://localhost:5000/auth/callback"
    )

    # Server-level Chess.com credentials (cookie-based, optional fallback)
    # Obtain from your browser after logging into Chess.com.
    CHESSCOM_SERVER_ACCESS_TOKEN = os.environ.get(
        "CHESSCOM_SERVER_ACCESS_TOKEN", ""
    )
    CHESSCOM_SERVER_PHPSESSID = os.environ.get("CHESSCOM_SERVER_PHPSESSID", "")

    # User-Agent sent with all API requests
    # (Chess.com requires a descriptive UA)
    USER_AGENT = "chessclub-web/1.0 (https://github.com/cmellojr/chessclub-web)"
