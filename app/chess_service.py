"""Wrapper around the chessclub library.

Provides :func:`make_client` which creates a :class:`ChessComClient`
authenticated with the best available credentials, mirroring the
chessclub CLI pattern:

* Server cookie credentials (``CHESSCOM_SERVER_ACCESS_TOKEN`` +
  ``CHESSCOM_SERVER_PHPSESSID``) are used as the **base** layer, because
  the Chess.com internal ``/callback/`` API requires session cookies and
  **rejects** OAuth Bearer tokens.
* If the user is also logged in via OAuth, the Bearer token is injected as
  an additional ``Authorization`` header on top of the cookie auth.
* If no server cookies are configured, OAuth alone is used as a fallback
  (gives access to the public API but not internal endpoints).
* If nothing is available, the client operates without credentials.
"""

import time

from chessclub.auth import AuthCredentials, AuthProvider
from chessclub.core.exceptions import AuthenticationRequiredError
from chessclub.providers.chesscom import ChessComClient, ChessComCookieAuth
from flask import current_app


class _SessionOAuthProvider(AuthProvider):
    """AuthProvider backed by an OAuth token stored in a Flask session dict."""

    def __init__(self, token_data: dict):
        self._token = token_data

    def get_credentials(self) -> AuthCredentials:
        if not self.is_authenticated():
            raise AuthenticationRequiredError("No valid token in session")
        return AuthCredentials(
            headers={"Authorization": f"Bearer {self._token['access_token']}"}
        )

    def is_authenticated(self) -> bool:
        if not self._token or "access_token" not in self._token:
            return False
        expires_at = self._token.get("expires_at", 0)
        return time.time() < (expires_at - 60)  # 60-second buffer


def make_client(session_data: dict) -> ChessComClient:
    """Create a :class:`ChessComClient` with the best available credentials.

    Resolution order:
    1. Server cookie credentials as base auth (required for internal API),
       with user OAuth Bearer injected as an additional header if available.
    2. User OAuth token only (public API access; internal endpoints will fail).
    3. No auth (public API only).

    Args:
        session_data: The Flask ``session`` object (or any dict with the
            same keys).

    Returns:
        An authenticated (or unauthenticated) :class:`ChessComClient`.
    """
    user_agent = current_app.config["USER_AGENT"]
    server_token = current_app.config.get("CHESSCOM_SERVER_ACCESS_TOKEN", "")
    server_sessid = current_app.config.get("CHESSCOM_SERVER_PHPSESSID", "")

    token_data = session_data.get("oauth_token")
    oauth_provider = _SessionOAuthProvider(token_data) if token_data else None

    if server_token and server_sessid:
        # Base auth: session cookies (required for /callback/ internal API)
        auth = ChessComCookieAuth(
            access_token=server_token, phpsessid=server_sessid
        )
        client = ChessComClient(user_agent=user_agent, auth=auth)
        # Additionally inject OAuth Bearer when the user is personally logged in
        if oauth_provider and oauth_provider.is_authenticated():
            creds = oauth_provider.get_credentials()
            client.session.headers.update(creds.headers)
        return client

    # Fallback: OAuth only (internal /callback/ endpoints will be unavailable)
    if oauth_provider and oauth_provider.is_authenticated():
        return ChessComClient(user_agent=user_agent, auth=oauth_provider)

    # Public only
    return ChessComClient(user_agent=user_agent)


def is_authenticated(session_data: dict) -> bool:
    """Return True if valid credentials are available."""
    server_token = current_app.config.get("CHESSCOM_SERVER_ACCESS_TOKEN", "")
    server_sessid = current_app.config.get("CHESSCOM_SERVER_PHPSESSID", "")
    if server_token and server_sessid:
        return True
    token_data = session_data.get("oauth_token")
    return bool(
        token_data and _SessionOAuthProvider(token_data).is_authenticated()
    )
