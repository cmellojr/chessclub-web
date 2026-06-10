"""Tests for the chess_service layer with mocked chessclub library."""

from app.chess_service import is_authenticated, make_client


class TestMakeClient:
    """Tests for the make_client function."""

    def test_make_client_unauthenticated(self, app):
        """make_client returns an unauthenticated client without credentials."""
        with app.app_context():
            client = make_client({})
        assert client is not None

    def test_is_authenticated_false_without_credentials(self, app):
        """is_authenticated returns False when no credentials are available."""
        with app.app_context():
            result = is_authenticated({})
        assert result is False

    def test_make_client_with_empty_session(self, app):
        """make_client handles an empty session without error."""
        with app.app_context():
            client = make_client({})
        assert client is not None
        assert hasattr(client, "session")

    def test_make_client_with_expired_oauth(self, app):
        """make_client handles expired OAuth token gracefully."""
        session_data = {
            "oauth_token": {
                "access_token": "expired-token",
                "expires_at": 0,  # expired
            }
        }
        with app.app_context():
            client = make_client(session_data)
        assert client is not None
