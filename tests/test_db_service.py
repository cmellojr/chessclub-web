"""Unit tests for the database service layer."""

import threading

from chessclub.core.models import Club, Member

from app.db_service import get_club, get_members, upsert_club, upsert_members


class TestClubCrud:
    """Tests for club create/read operations."""

    def test_db_upsert_and_get_club(self, db):
        """upsert_club persists a club and get_club retrieves it."""
        club = Club(
            id="test-club",
            provider_id="123",
            name="Test Club",
            description="A test club",
            country="US",
            url="https://chess.com/club/test-club",
            members_count=10,
            created_at=1600000000,
            location="Testville",
            matches_count=5,
        )
        upsert_club(club)
        retrieved = get_club("test-club")
        assert retrieved is not None
        assert retrieved.name == "Test Club"
        assert retrieved.id == "test-club"

    def test_db_upsert_updates_existing(self, db):
        """upsert_club updates an existing club instead of duplicate."""
        club = Club(
            id="update-club",
            provider_id="123",
            name="Original Name",
            description="Original",
            country="US",
            url="https://chess.com/club/update-club",
            members_count=5,
            created_at=1600000000,
            location="Nowhere",
            matches_count=2,
        )
        upsert_club(club)
        club.name = "Updated Name"
        club.members_count = 20
        upsert_club(club)
        retrieved = get_club("update-club")
        assert retrieved is not None
        assert retrieved.name == "Updated Name"
        assert retrieved.members_count == 20

    def test_db_get_nonexistent_club(self, db):
        """get_club returns None for a nonexistent club."""
        result = get_club("nonexistent")
        assert result is None

    def test_db_service_large_input(self, db):
        """upsert_members handles a large member list without crashing."""
        upsert_club(
            Club(
                id="large-club",
                provider_id="999",
                name="Large Club",
                description="",
                country="US",
                url="https://chess.com/club/large-club",
                members_count=10000,
                created_at=1600000000,
                location="Big City",
                matches_count=0,
            )
        )
        members = [
            Member(
                username=f"player{i:05d}",
                rating=1500 + (i % 500),
                title="" if i % 10 else "GM",
                joined_at=1600000000 + i,
                activity="last week",
            )
            for i in range(10000)
        ]
        upsert_members("large-club", members)
        retrieved = get_members("large-club")
        assert retrieved is not None
        assert len(retrieved) == 10000

    def test_concurrent_db_reads(self, db, app):
        """Multiple threads can read get_club simultaneously without errors."""
        upsert_club(
            Club(
                id="concurrent-club",
                provider_id="555",
                name="Concurrent Club",
                description="",
                country="US",
                url="https://chess.com/club/concurrent-club",
                members_count=0,
                created_at=1600000000,
                location="Threadville",
                matches_count=0,
            )
        )

        results = []
        errors = []

        def reader():
            try:
                with app.app_context():
                    result = get_club("concurrent-club")
                    results.append(result)
            except Exception as exc:  # noqa: BLE001 — test helper, not app code
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert all(r is not None for r in results)
