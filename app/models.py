"""SQLAlchemy ORM models for persistent chess club data.

Each model maps 1:1 to a chessclub library dataclass, enabling
permanent storage that survives library cache expiration.
"""

from app.extensions import db


class ClubModel(db.Model):
    """Persistent club overview data."""

    __tablename__ = "clubs"

    id = db.Column(db.String, primary_key=True)  # slug
    provider_id = db.Column(db.String, nullable=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text, nullable=True)
    country = db.Column(db.String, nullable=True)
    url = db.Column(db.String, nullable=True)
    members_count = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String, nullable=True)
    matches_count = db.Column(db.Integer, nullable=True)

    members = db.relationship(
        "MemberModel", backref="club", cascade="all, delete-orphan"
    )
    tournaments = db.relationship(
        "TournamentModel", backref="club", cascade="all, delete-orphan"
    )
    records = db.relationship(
        "ClubRecordModel", backref="club", cascade="all, delete-orphan"
    )


class MemberModel(db.Model):
    """Persistent club member data."""

    __tablename__ = "members"

    club_id = db.Column(db.String, db.ForeignKey("clubs.id"), primary_key=True)
    username = db.Column(db.String, primary_key=True)
    rating = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String, nullable=True)
    joined_at = db.Column(db.Integer, nullable=True)
    activity = db.Column(db.String, nullable=True)


class TournamentModel(db.Model):
    """Persistent tournament metadata."""

    __tablename__ = "tournaments"

    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    tournament_type = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False)
    start_date = db.Column(db.Integer, nullable=True)
    end_date = db.Column(db.Integer, nullable=True)
    player_count = db.Column(db.Integer, nullable=False, default=0)
    winner_username = db.Column(db.String, nullable=True)
    winner_score = db.Column(db.Float, nullable=True)
    club_slug = db.Column(db.String, db.ForeignKey("clubs.id"), nullable=True)
    url = db.Column(db.String, nullable=True)

    results = db.relationship(
        "TournamentResultModel",
        backref="tournament",
        cascade="all, delete-orphan",
    )
    games = db.relationship(
        "GameModel", backref="tournament", cascade="all, delete-orphan"
    )


class TournamentResultModel(db.Model):
    """Persistent tournament result (one row per player per tournament)."""

    __tablename__ = "tournament_results"

    tournament_id = db.Column(
        db.String,
        db.ForeignKey("tournaments.id"),
        primary_key=True,
    )
    player = db.Column(db.String, primary_key=True)
    position = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float, nullable=True)
    rating = db.Column(db.Integer, nullable=True)


class GameModel(db.Model):
    """Persistent game data (individual game within a tournament)."""

    __tablename__ = "games"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    white = db.Column(db.String, nullable=False)
    black = db.Column(db.String, nullable=False)
    result = db.Column(db.String, nullable=False)
    opening_eco = db.Column(db.String, nullable=True)
    pgn = db.Column(db.Text, nullable=True)
    played_at = db.Column(db.Integer, nullable=True)
    white_accuracy = db.Column(db.Float, nullable=True)
    black_accuracy = db.Column(db.Float, nullable=True)
    tournament_id = db.Column(
        db.String, db.ForeignKey("tournaments.id"), nullable=True
    )
    url = db.Column(db.String, nullable=True)

    __table_args__ = (
        db.Index("ix_games_tournament", "tournament_id"),
        db.Index("ix_games_players", "white", "black"),
    )


class ClubRecordModel(db.Model):
    """Persistent pre-computed club records."""

    __tablename__ = "club_records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    club_id = db.Column(db.String, db.ForeignKey("clubs.id"), nullable=False)
    category = db.Column(db.String, nullable=False)
    value = db.Column(db.String, nullable=False)
    player = db.Column(db.String, nullable=True)
    detail = db.Column(db.String, nullable=True)
    date = db.Column(db.Integer, nullable=True)
