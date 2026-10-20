"""Models representing taste comparison and recommendation results between two users."""

from dataclasses import dataclass, field
from backloggd.models.game import GameEntry


@dataclass(slots=True, frozen=True)
class RatingDisagreement:
    """Represents a game where two users strongly disagreed on their rating."""
    game: GameEntry
    user1_rating: float
    user2_rating: float
    difference: float


@dataclass(slots=True, frozen=True)
class MatchComparison:
    """Full comparison result between two Backloggd users."""
    user1: str
    user2: str
    similarity_score: float
    library_score: float
    rating_score: float
    shared_games_count: int
    mutually_rated_count: int

    # Taste highlights
    mutual_favorites: list[GameEntry] = field(default_factory=list)
    disagreements: list[RatingDisagreement] = field(default_factory=list)
    recommendations_for_user1: list[GameEntry] = field(default_factory=list)
    recommendations_for_user2: list[GameEntry] = field(default_factory=list)
