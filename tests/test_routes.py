"""Smoke tests for all application routes."""

from unittest.mock import patch

from chessclub.core.exceptions import ChessclubError


class TestHomepage:
    """Tests for the homepage route."""

    def test_index_returns_200(self, client):
        """GET / returns 200 with the expected content."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Chess Club Portal" in response.data


class TestSearch:
    """Tests for the search route."""

    def test_search_with_slug_redirects(self, client):
        """GET /search?slug=test redirects to /club/test."""
        response = client.get("/search?slug=test")
        assert response.status_code == 302
        assert "/club/test" in response.location

    def test_search_without_slug_flashes(self, client):
        """GET /search without slug redirects with a flash message."""
        response = client.get("/search")
        assert response.status_code == 302
        assert response.location.endswith("/")

    def test_search_sql_injection_attempt(self, client):
        """Slug with SQL-like content is handled without leaking data."""
        response = client.get("/search?slug=' OR 1=1--")
        assert response.status_code == 302
        assert "/club/'%20OR%201=1--" in response.location


class TestClubOverview:
    """Tests for the club overview route."""

    def test_club_in_db_returns_200(self, client, club_in_db):
        """GET /club/test-club returns 200 when club exists in DB."""
        response = client.get("/club/test-club")
        assert response.status_code == 200

    def test_nonexistent_club_redirects(self, client):
        """GET /club/nonexistent redirects when club is not in DB."""
        with patch("app.club.ClubService") as mock_club_svc:
            mock_club_svc.return_value.get_club.side_effect = ChessclubError(
                "Not found"
            )
            response = client.get("/club/nonexistent")
            assert response.status_code == 302

    def test_slug_path_traversal_attempt(self, client):
        """Path traversal in slug is handled safely."""
        response = client.get("/club/../config")
        assert response.status_code == 404


class TestClubMembers:
    """Tests for the club members route."""

    def test_members_with_club_in_db(self, client, club_in_db):
        """GET /club/test-club/members returns 200 for a known club."""
        response = client.get("/club/test-club/members")
        assert response.status_code == 200

    def test_members_nonexistent_club_redirects(self, client):
        """GET /club/nonexistent/members redirects for unknown club."""
        with patch("app.club.ClubService") as mock_club_svc:
            mock_club_svc.return_value.get_club.side_effect = ChessclubError(
                "Not found"
            )
            response = client.get("/club/nonexistent/members")
            assert response.status_code == 302


class TestClubTournaments:
    """Tests for the club tournaments route."""

    def test_tournaments_with_club_in_db(self, client, club_in_db):
        """GET /club/test-club/tournaments returns 200 for a known club."""
        response = client.get("/club/test-club/tournaments")
        assert response.status_code == 200

    def test_tournaments_nonexistent_club_redirects(self, client):
        """GET /club/nonexistent/tournaments redirects."""
        response = client.get("/club/nonexistent/tournaments")
        assert response.status_code == 302


class TestClubLeaderboard:
    """Tests for the club leaderboard route."""

    def test_leaderboard_with_club_in_db(self, client, club_in_db):
        """GET /club/test-club/leaderboard returns 200 for a known club."""
        response = client.get("/club/test-club/leaderboard")
        assert response.status_code == 200

    def test_leaderboard_nonexistent_club_redirects(self, client):
        """GET /club/nonexistent/leaderboard redirects."""
        response = client.get("/club/nonexistent/leaderboard")
        assert response.status_code == 302

    def test_leaderboard_with_year_filter(self, client, club_in_db):
        """Leaderboard with year filter works."""
        response = client.get("/club/test-club/leaderboard?year=2024")
        assert response.status_code == 200


class TestClubMatchups:
    """Tests for the club matchups route."""

    def test_matchups_with_club_in_db(self, client, club_in_db):
        """GET /club/test-club/matchups returns 200 for a known club."""
        response = client.get("/club/test-club/matchups")
        assert response.status_code == 200

    def test_matchups_nonexistent_club_redirects(self, client):
        """GET /club/nonexistent/matchups redirects."""
        response = client.get("/club/nonexistent/matchups")
        assert response.status_code == 302


class TestClubAttendance:
    """Tests for the club attendance route."""

    def test_attendance_with_club_in_db(self, client, club_in_db):
        """GET /club/test-club/attendance returns 200 for a known club."""
        response = client.get("/club/test-club/attendance")
        assert response.status_code == 200

    def test_attendance_nonexistent_club_redirects(self, client):
        """GET /club/nonexistent/attendance redirects."""
        response = client.get("/club/nonexistent/attendance")
        assert response.status_code == 302


class TestClubRecords:
    """Tests for the club records route."""

    def test_records_with_club_in_db(self, client, club_in_db):
        """GET /club/test-club/records returns 200 for a known club."""
        response = client.get("/club/test-club/records")
        assert response.status_code == 200

    def test_records_nonexistent_club_redirects(self, client):
        """GET /club/nonexistent/records redirects."""
        response = client.get("/club/nonexistent/records")
        assert response.status_code == 302


class TestPlayerRatingHistory:
    """Tests for the player rating history route."""

    def test_rating_history_without_club_redirects(self, client):
        """GET /player/username/rating-history without club param redirects."""
        response = client.get("/player/testuser/rating-history")
        assert response.status_code == 302

    def test_rating_history_with_club_in_db(self, client, club_in_db):
        """GET /player/username/rating-history with club param returns 200."""
        response = client.get("/player/testuser/rating-history?club=test-club")
        assert response.status_code == 200

    def test_rating_history_nonexistent_club_redirects(self, client):
        """Rating history for nonexistent club redirects to auth setup."""
        response = client.get(
            "/player/testuser/rating-history?club=nonexistent"
        )
        assert response.status_code == 302


class TestAuth:
    """Tests for authentication routes."""

    def test_setup_page_returns_200(self, client):
        """GET /auth/setup returns 200."""
        response = client.get("/auth/setup")
        assert response.status_code == 200

    def test_login_without_oauth_redirects(self, client):
        """GET /auth/login without OAuth configured redirects to setup."""
        response = client.get("/auth/login")
        assert response.status_code == 302

    def test_callback_without_code_redirects(self, client):
        """GET /auth/callback without code param redirects."""
        response = client.get("/auth/callback")
        assert response.status_code == 302

    def test_logout_redirects(self, client):
        """GET /auth/logout redirects to home."""
        response = client.get("/auth/logout")
        assert response.status_code == 302


class TestAdmin:
    """Tests for admin routes."""

    @staticmethod
    def _login_admin(client):
        """Log in as admin, handling CSRF token."""
        client.get("/admin/login")
        with client.session_transaction() as sess:
            token = sess.get("csrf_token")
        client.post(
            "/admin/login",
            data={"password": "test-password", "csrf_token": token},
        )

    def test_admin_login_page_returns_200(self, client):
        """GET /admin/login returns 200 when admin password is set."""
        response = client.get("/admin/login")
        assert response.status_code == 200

    def test_admin_without_password_disabled(self, app, client):
        """Admin is disabled when ADMIN_PASSWORD is empty."""
        app.config["ADMIN_PASSWORD"] = ""
        response = client.get("/admin/")
        assert response.status_code == 302
        assert response.location.endswith("/")

    def test_admin_without_login_redirects(self, client):
        """GET /admin/ without session redirects to login."""
        response = client.get("/admin/")
        assert response.status_code == 302
        assert "login" in response.location

    def test_admin_dashboard_after_login(self, client):
        """Logged-in admin can access the dashboard."""
        self._login_admin(client)
        response = client.get("/admin/")
        assert response.status_code == 200

    def test_admin_clubs_after_login(self, client):
        """Logged-in admin can access the clubs page."""
        self._login_admin(client)
        response = client.get("/admin/clubs")
        assert response.status_code == 200

    def test_admin_logout_redirects(self, client):
        """Admin logout redirects to home."""
        response = client.get("/admin/logout")
        assert response.status_code == 302

    def test_admin_clubs_add_post_redirects_when_unauthenticated(self, client):
        """POST /admin/clubs/add without auth redirects to login."""
        response = client.post("/admin/clubs/add", data={"slug": "test-club"})
        assert response.status_code == 302
        assert "login" in response.location

    def test_admin_clubs_remove_post_redirects_when_unauthenticated(
        self, client,
    ):
        """POST /admin/clubs/remove without auth redirects to login."""
        response = client.post(
            "/admin/clubs/remove", data={"slug": "test-club"}
        )
        assert response.status_code == 302
        assert "login" in response.location

    def test_admin_sync_post_redirects_when_unauthenticated(self, client):
        """POST /admin/sync without auth redirects to login."""
        response = client.post("/admin/sync")
        assert response.status_code == 302
        assert "login" in response.location

    def test_admin_sync_games_post_redirects_when_unauthenticated(self, client):
        """POST /admin/sync-games/<slug> without auth redirects to login."""
        response = client.post("/admin/sync-games/test-club")
        assert response.status_code == 302
        assert "login" in response.location


class TestErrorHandlers:
    """Tests for custom error handlers and the /health endpoint."""

    def test_404_custom_page(self, client):
        """Nonexistent route returns custom 404 template."""
        response = client.get("/pagina-inexistente")
        assert response.status_code == 404
        assert b"Page not found" in response.data

    def test_health_endpoint(self, client):
        """GET /health returns 200 with JSON status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_health_returns_sync_info(self, client):
        """GET /health returns sync info in JSON response."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert "sync" in data
        assert "last_run" in data["sync"]
        assert "running" in data["sync"]

    def test_health_no_auth_required(self, client):
        """GET /health does not require authentication."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.is_json

    def test_403_custom_page(self, client):
        """Custom 403 page is rendered when abort(403) is called."""
        from flask import abort

        @client.application.route("/test-forbidden")
        def test_forbidden():
            abort(403)

        response = client.get("/test-forbidden")
        assert response.status_code == 403
        assert b"Access forbidden" in response.data

    def test_errorhandler_does_not_leak(self, app, client):
        """Forced 500 returns custom template, not a traceback."""
        app.config["PROPAGATE_EXCEPTIONS"] = False
        from unittest.mock import patch

        with patch("app.club.db_service.get_club", return_value=None):
            with patch(
                "app.club.chess_service.make_client",
                side_effect=RuntimeError("Boom!"),
            ):
                response = client.get("/club/nonexistent")
                assert response.status_code == 500
                assert b"Something went wrong" in response.data
                assert b"Traceback" not in response.data
