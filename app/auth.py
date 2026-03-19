"""Blueprint for Chess.com authentication.

Supports two credential types, mirroring the chessclub CLI:

* **OAuth 2.0 PKCE** (per-user): the user logs in via Chess.com and an
  access token is stored in the Flask session.  Requires
  ``CHESSCOM_OAUTH_CLIENT_ID`` to be set.  Enables public-API endpoints
  that accept Bearer tokens.

* **Session cookies** (server-level): ``ACCESS_TOKEN`` + ``PHPSESSID``
  are configured in ``.env``.  Required for the Chess.com internal web
  API (``/callback/`` endpoints used for tournaments, leaderboard, etc.),
  which **rejects** OAuth Bearer tokens.

When both are present the client uses cookies as the base auth and adds
the OAuth Bearer header on top — exactly as the chessclub CLI does.
"""

import base64
import hashlib
import secrets
import time
import urllib.parse

import requests
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

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

_CHESSCOM_AUTH_URL = "https://oauth.chess.com/authorize"
_CHESSCOM_TOKEN_URL = "https://oauth.chess.com/token"


@auth_bp.route("/login")
def login():
    """Initiate the Chess.com OAuth 2.0 PKCE authorization flow.

    Requires ``CHESSCOM_OAUTH_CLIENT_ID`` to be configured.  Generates a
    PKCE pair, stores the verifier in the session, then redirects to the
    Chess.com authorization page.
    """
    client_id = current_app.config.get("CHESSCOM_OAUTH_CLIENT_ID", "")
    if not client_id:
        flash(
            "OAuth login not configured. Set CHESSCOM_OAUTH_CLIENT_ID in .env.",
            "warning",
        )
        return redirect(url_for("auth.setup"))

    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    session["oauth_code_verifier"] = code_verifier
    session["oauth_next"] = request.args.get("next") or url_for("club.index")

    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": current_app.config["OAUTH_REDIRECT_URI"],
            "response_type": "code",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return redirect(f"{_CHESSCOM_AUTH_URL}?{params}")


@auth_bp.route("/callback")
def callback():
    """Handle the OAuth redirect and exchange the authorization code for tokens.

    Stores the access token, refresh token, and expiry in the Flask session.
    """
    error = request.args.get("error")
    if error:
        desc = request.args.get("error_description", error)
        flash(
            f"Chess.com authentication error: {desc}",
            "danger",
        )
        return redirect(url_for("club.index"))

    code = request.args.get("code")
    code_verifier = session.pop("oauth_code_verifier", None)
    next_url = session.pop("oauth_next", url_for("club.index"))

    if not code or not code_verifier:
        flash("Invalid OAuth flow. Please try again.", "danger")
        return redirect(url_for("club.index"))

    try:
        resp = requests.post(
            _CHESSCOM_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": current_app.config["OAUTH_REDIRECT_URI"],
                "client_id": current_app.config["CHESSCOM_OAUTH_CLIENT_ID"],
                "code_verifier": code_verifier,
            },
            timeout=30,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except requests.RequestException as exc:
        flash(f"Token exchange error: {exc}", "danger")
        return redirect(url_for("club.index"))

    session["oauth_token"] = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
        "expires_at": time.time() + token_data.get("expires_in", 3600),
    }
    session["chess_username"] = (
        token_data.get("username") or token_data.get("login") or ""
    )

    flash("Successfully connected to Chess.com!", "success")
    return redirect(next_url)


@auth_bp.route("/logout")
def logout():
    """Clear the user's OAuth credentials from the session."""
    session.pop("oauth_token", None)
    session.pop("chess_username", None)
    flash("Disconnected from Chess.com.", "info")
    return redirect(url_for("club.index"))


@auth_bp.route("/setup")
def setup():
    """Display instructions for configuring server-side cookie credentials."""
    return render_template("auth/setup.html")
