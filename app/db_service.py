"""Data access layer for persistent chess club storage.

Write functions are called by the sync worker to persist data from the
chessclub library. Read functions are called by routes and return library
dataclass instances so that templates need zero changes.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from chessclub.core.models import (
    AttendanceRecord,
    Club,
    ClubRecord,
    Game,
    Matchup,
    Member,
    PlayerStats,
    RatingSnapshot,
    Tournament,
    TournamentResult,
)

from app.extensions import db
from app.models import (
    ClubModel,
    ClubRecordModel,
    GameModel,
    MemberModel,
    TournamentModel,
    TournamentResultModel,
)

log = logging.getLogger(__name__)


# ===================================================================
# Write functions (called by sync worker)
# ===================================================================


def upsert_club(club: Club) -> None:
    """Insert or update a club record.

    Args:
        club: Club dataclass from the chessclub library.
    """
    row = db.session.get(ClubModel, club.id)
    if row is None:
        row = ClubModel(id=club.id)
        db.session.add(row)
    row.provider_id = club.provider_id
    row.name = club.name
    row.description = club.description
    row.country = club.country
    row.url = club.url
    row.members_count = club.members_count
    row.created_at = club.created_at
    row.location = club.location
    row.matches_count = club.matches_count
    db.session.commit()


def upsert_members(club_id: str, members: list[Member]) -> None:
    """Replace all members for a club.

    Args:
        club_id: The club slug.
        members: List of Member dataclasses.
    """
    MemberModel.query.filter_by(club_id=club_id).delete()
    for m in members:
        db.session.add(
            MemberModel(
                club_id=club_id,
                username=m.username,
                rating=m.rating,
                title=m.title,
                joined_at=m.joined_at,
                activity=m.activity,
            )
        )
    db.session.commit()


def upsert_tournaments(tournaments: list[Tournament]) -> None:
    """Insert or update tournament records.

    Args:
        tournaments: List of Tournament dataclasses.
    """
    for t in tournaments:
        row = db.session.get(TournamentModel, t.id)
        if row is None:
            row = TournamentModel(id=t.id)
            db.session.add(row)
        row.name = t.name
        row.tournament_type = t.tournament_type
        row.status = t.status
        row.start_date = t.start_date
        row.end_date = t.end_date
        row.player_count = t.player_count
        row.winner_username = t.winner_username
        row.winner_score = t.winner_score
        row.club_slug = t.club_slug
        row.url = t.url
    db.session.commit()


def upsert_results(results: list[TournamentResult]) -> None:
    """Insert or update tournament results.

    Args:
        results: List of TournamentResult dataclasses.
    """
    for r in results:
        row = db.session.get(TournamentResultModel, (r.tournament_id, r.player))
        if row is None:
            row = TournamentResultModel(
                tournament_id=r.tournament_id, player=r.player
            )
            db.session.add(row)
        row.position = r.position
        row.score = r.score
        row.rating = r.rating
    db.session.commit()


def upsert_games(tournament_id: str, games: list[Game]) -> None:
    """Replace all games for a tournament.

    Args:
        tournament_id: The tournament identifier.
        games: List of Game dataclasses.
    """
    GameModel.query.filter_by(tournament_id=tournament_id).delete()
    for g in games:
        db.session.add(
            GameModel(
                white=g.white,
                black=g.black,
                result=g.result,
                opening_eco=g.opening_eco,
                pgn=g.pgn,
                played_at=g.played_at,
                white_accuracy=g.white_accuracy,
                black_accuracy=g.black_accuracy,
                tournament_id=tournament_id,
                url=g.url,
            )
        )
    db.session.commit()


def store_records(club_id: str, records: list[ClubRecord]) -> None:
    """Replace all records for a club.

    Args:
        club_id: The club slug.
        records: List of ClubRecord dataclasses.
    """
    ClubRecordModel.query.filter_by(club_id=club_id).delete()
    for r in records:
        db.session.add(
            ClubRecordModel(
                club_id=club_id,
                category=r.category,
                value=r.value,
                player=r.player,
                detail=r.detail,
                date=r.date,
            )
        )
    db.session.commit()


# ===================================================================
# Read functions (called by routes)
# ===================================================================


def get_club(slug: str) -> Club | None:
    """Load a club from the database.

    Args:
        slug: The club slug.

    Returns:
        A Club dataclass, or None if not found.
    """
    row = db.session.get(ClubModel, slug)
    if row is None:
        return None
    return Club(
        id=row.id,
        provider_id=row.provider_id,
        name=row.name,
        description=row.description,
        country=row.country,
        url=row.url,
        members_count=row.members_count,
        created_at=row.created_at,
        location=row.location,
        matches_count=row.matches_count,
    )


def get_members(slug: str) -> list[Member] | None:
    """Load club members from the database.

    Args:
        slug: The club slug.

    Returns:
        A list of Member dataclasses, or None if the club has
        no members stored.
    """
    rows = MemberModel.query.filter_by(club_id=slug).all()
    if not rows:
        return None
    return [
        Member(
            username=r.username,
            rating=r.rating,
            title=r.title,
            joined_at=r.joined_at,
            activity=r.activity,
        )
        for r in rows
    ]


def get_tournaments(slug: str) -> list[Tournament] | None:
    """Load club tournaments from the database.

    Args:
        slug: The club slug.

    Returns:
        A list of Tournament dataclasses, or None if none stored.
    """
    rows = (
        TournamentModel.query.filter_by(club_slug=slug)
        .order_by(TournamentModel.end_date.desc())
        .all()
    )
    if not rows:
        return None
    return [
        Tournament(
            id=r.id,
            name=r.name,
            tournament_type=r.tournament_type,
            status=r.status,
            start_date=r.start_date,
            end_date=r.end_date,
            player_count=r.player_count,
            winner_username=r.winner_username,
            winner_score=r.winner_score,
            club_slug=r.club_slug,
            url=r.url,
        )
        for r in rows
    ]


def get_leaderboard(
    slug: str,
    year: int | None = None,
    month: int | None = None,
) -> list[PlayerStats] | None:
    """Compute leaderboard from stored tournament results.

    Groups results by player, filtering by tournaments that belong
    to the given club and optionally by year/month.

    Args:
        slug: The club slug.
        year: Optional year filter.
        month: Optional month filter.

    Returns:
        A list of PlayerStats sorted by total_score descending,
        or None if no results are stored.
    """
    import datetime as dt

    query = (
        db.session.query(TournamentResultModel)
        .join(TournamentModel)
        .filter(TournamentModel.club_slug == slug)
        .filter(TournamentModel.status == "finished")
    )

    if year is not None:
        start_ts = int(dt.datetime(year, 1, 1, tzinfo=dt.UTC).timestamp())
        end_ts = int(dt.datetime(year + 1, 1, 1, tzinfo=dt.UTC).timestamp())
        if month is not None:
            start_ts = int(
                dt.datetime(year, month, 1, tzinfo=dt.UTC).timestamp()
            )
            if month == 12:
                end_ts = int(
                    dt.datetime(year + 1, 1, 1, tzinfo=dt.UTC).timestamp()
                )
            else:
                end_ts = int(
                    dt.datetime(year, month + 1, 1, tzinfo=dt.UTC).timestamp()
                )
        query = query.filter(
            TournamentModel.end_date >= start_ts,
            TournamentModel.end_date < end_ts,
        )

    results = query.all()
    if not results:
        return None

    # Group by player
    player_data: dict[str, list[TournamentResultModel]] = defaultdict(list)
    for r in results:
        player_data[r.player].append(r)

    stats = []
    for username, rows in player_data.items():
        tournaments_played = len(rows)
        wins = sum(1 for r in rows if r.position == 1)
        total_score = sum(r.score or 0 for r in rows)
        avg_score = (
            total_score / tournaments_played if tournaments_played else 0
        )
        stats.append(
            PlayerStats(
                username=username,
                tournaments_played=tournaments_played,
                wins=wins,
                total_score=total_score,
                avg_score=round(avg_score, 2),
            )
        )

    stats.sort(key=lambda s: s.total_score, reverse=True)
    return stats


def get_matchups(slug: str, last_n: int | None = None) -> list[Matchup] | None:
    """Compute head-to-head matchups from stored games.

    Args:
        slug: The club slug.
        last_n: If set, only consider games from the last N
            tournaments.

    Returns:
        A list of Matchup dataclasses sorted by total_games
        descending, or None if no games are stored.
    """
    # Get club tournaments (newest first)
    t_query = (
        TournamentModel.query.filter_by(club_slug=slug)
        .filter_by(status="finished")
        .order_by(TournamentModel.end_date.desc())
    )
    if last_n:
        t_query = t_query.limit(last_n)
    tournament_ids = [t.id for t in t_query.all()]

    if not tournament_ids:
        return None

    games = GameModel.query.filter(
        GameModel.tournament_id.in_(tournament_ids)
    ).all()

    if not games:
        return None

    # Group by player pair (alphabetical order)
    pair_data: dict[tuple[str, str], dict] = {}
    for g in games:
        a, b = sorted([g.white.lower(), g.black.lower()])
        key = (a, b)
        if key not in pair_data:
            pair_data[key] = {
                "a": a,
                "b": b,
                "wins_a": 0,
                "wins_b": 0,
                "draws": 0,
                "last_played": None,
            }
        pd = pair_data[key]

        if g.result == "1/2-1/2":
            pd["draws"] += 1
        elif g.result == "1-0":
            winner = g.white.lower()
            if winner == a:
                pd["wins_a"] += 1
            else:
                pd["wins_b"] += 1
        elif g.result == "0-1":
            winner = g.black.lower()
            if winner == a:
                pd["wins_a"] += 1
            else:
                pd["wins_b"] += 1

        if g.played_at and (
            pd["last_played"] is None or g.played_at > pd["last_played"]
        ):
            pd["last_played"] = g.played_at

    matchups = [
        Matchup(
            player_a=d["a"],
            player_b=d["b"],
            wins_a=d["wins_a"],
            wins_b=d["wins_b"],
            draws=d["draws"],
            total_games=d["wins_a"] + d["wins_b"] + d["draws"],
            last_played=d["last_played"],
        )
        for d in pair_data.values()
    ]
    matchups.sort(key=lambda m: m.total_games, reverse=True)
    return matchups


def get_attendance(
    slug: str, last_n: int | None = None
) -> list[AttendanceRecord] | None:
    """Compute attendance from stored tournament results.

    Args:
        slug: The club slug.
        last_n: If set, only consider the last N tournaments.

    Returns:
        A list of AttendanceRecord dataclasses sorted by
        participation_pct descending, or None if no data stored.
    """
    t_query = (
        TournamentModel.query.filter_by(club_slug=slug)
        .filter_by(status="finished")
        .order_by(TournamentModel.end_date.desc())
    )
    if last_n:
        t_query = t_query.limit(last_n)
    tournaments = t_query.all()

    if not tournaments:
        return None

    tournament_ids = [t.id for t in tournaments]
    total_tournaments = len(tournament_ids)

    # Get all results for these tournaments
    results = TournamentResultModel.query.filter(
        TournamentResultModel.tournament_id.in_(tournament_ids)
    ).all()

    if not results:
        return None

    # Map tournament_id to its chronological index (0 = oldest)
    sorted_ids = list(reversed(tournament_ids))  # oldest first
    t_index = {tid: i for i, tid in enumerate(sorted_ids)}

    # Group by player
    player_tournaments: dict[str, set[str]] = defaultdict(set)
    for r in results:
        player_tournaments[r.player].add(r.tournament_id)

    records = []
    for username, t_set in player_tournaments.items():
        tournaments_played = len(t_set)
        pct = (
            tournaments_played / total_tournaments * 100
            if total_tournaments
            else 0
        )

        # Compute streaks
        attended = sorted(t_index[tid] for tid in t_set if tid in t_index)
        current_streak = 0
        max_streak = 0

        if attended:
            # Current streak: count from the most recent tournament
            # backwards
            streak = 0
            for i in range(total_tournaments - 1, -1, -1):
                if i in attended:
                    streak += 1
                else:
                    break
            current_streak = streak

            # Max streak: longest consecutive run
            streak = 1
            max_s = 1
            for i in range(1, len(attended)):
                if attended[i] == attended[i - 1] + 1:
                    streak += 1
                    max_s = max(max_s, streak)
                else:
                    streak = 1
            max_streak = max(max_s, streak) if attended else 0

        records.append(
            AttendanceRecord(
                username=username,
                tournaments_played=tournaments_played,
                total_tournaments=total_tournaments,
                participation_pct=round(pct, 1),
                current_streak=current_streak,
                max_streak=max_streak,
            )
        )

    records.sort(key=lambda r: r.participation_pct, reverse=True)
    return records


def get_records(
    slug: str, last_n: int | None = None
) -> list[ClubRecord] | None:
    """Load pre-computed club records from the database.

    Args:
        slug: The club slug.
        last_n: Unused (records are pre-computed by the library).

    Returns:
        A list of ClubRecord dataclasses, or None if none stored.
    """
    rows = ClubRecordModel.query.filter_by(club_id=slug).all()
    if not rows:
        return None
    return [
        ClubRecord(
            category=r.category,
            value=r.value,
            player=r.player,
            detail=r.detail,
            date=r.date,
        )
        for r in rows
    ]


def get_rating_history(
    slug: str,
    username: str,
    last_n: int | None = None,
) -> list[RatingSnapshot] | None:
    """Compute rating history from stored tournament results.

    Args:
        slug: The club slug.
        username: The player's username.
        last_n: If set, only the last N tournaments.

    Returns:
        A list of RatingSnapshot dataclasses sorted by date,
        or None if no data stored.
    """
    query = (
        db.session.query(TournamentResultModel, TournamentModel)
        .join(TournamentModel)
        .filter(TournamentModel.club_slug == slug)
        .filter(TournamentModel.status == "finished")
        .filter(db.func.lower(TournamentResultModel.player) == username.lower())
        .order_by(TournamentModel.end_date.desc())
    )

    if last_n:
        query = query.limit(last_n)

    rows = query.all()
    if not rows:
        return None

    snapshots = [
        RatingSnapshot(
            tournament_id=r.tournament_id,
            tournament_name=t.name,
            tournament_type=t.tournament_type,
            tournament_date=t.end_date or t.start_date,
            rating=r.rating,
            position=r.position,
            score=r.score,
        )
        for r, t in rows
    ]

    # Return in chronological order (oldest first)
    snapshots.sort(key=lambda s: s.tournament_date or 0)
    return snapshots
