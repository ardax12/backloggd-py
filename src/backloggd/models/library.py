from dataclasses import dataclass, field
from typing import Iterator, Optional
from backloggd.models.game import GameEntry, GameStatus


@dataclass(slots=True, frozen=True)
class UserStats:
    """Statistical summary of a user's library and rating distribution."""
    total_games: int
    rated_count: int
    unrated_count: int
    average_rating: Optional[float]
    played_count: int
    playing_count: int
    backlog_count: int
    wishlist_count: int
    rating_distribution: dict[float, int] = field(default_factory=dict)


@dataclass
class UserLibrary:
    """Represents a collection of games in a user's library."""
    username: str
    games: dict[str, GameEntry] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.games)

    def __iter__(self) -> Iterator[GameEntry]:
        return iter(self.games.values())

    def __getitem__(self, slug: str) -> GameEntry:
        return self.games[slug]

    def __contains__(self, slug: str) -> bool:
        return slug in self.games

    def get(self, slug: str, default: Optional[GameEntry] = None) -> Optional[GameEntry]:
        """Lookup a game by slug."""
        return self.games.get(slug, default)

    def add(self, game: GameEntry) -> None:
        """Add or update a game entry in the library."""
        self.games[game.slug] = game

    def update(self, games: list[GameEntry]) -> None:
        """Add multiple game entries."""
        for g in games:
            self.games[g.slug] = g

    @property
    def slugs(self) -> set[str]:
        """Return set of all game slugs."""
        return set(self.games.keys())

    @property
    def rated_games(self) -> list[GameEntry]:
        """Return all games that have a user rating."""
        return [g for g in self.games.values() if g.is_rated]

    @property
    def unrated_games(self) -> list[GameEntry]:
        """Return all games without a rating."""
        return [g for g in self.games.values() if not g.is_rated]

    def filter(
        self,
        status: Optional[GameStatus | str] = None,
        min_rating: Optional[float] = None,
        max_rating: Optional[float] = None,
        is_liked: Optional[bool] = None,
    ) -> list[GameEntry]:
        """Filter library games based on rating, status, or like state."""
        results = list(self.games.values())

        if status is not None:
            status_val = status.value if isinstance(status, GameStatus) else str(status).lower()
            results = [g for g in results if g.status.value == status_val]

        if min_rating is not None:
            results = [g for g in results if g.rating is not None and g.rating >= min_rating]

        if max_rating is not None:
            results = [g for g in results if g.rating is not None and g.rating <= max_rating]

        if is_liked is not None:
            results = [g for g in results if g.is_liked == is_liked]

        return results

    def to_ratings_dict(self) -> dict[str, Optional[float]]:
        """Return a mapping of slug to rating (used by similarity algorithms)."""
        return {g.slug: g.rating for g in self.games.values()}

    def to_dict(self) -> list[dict]:
        """Convert all games in library to a list of dictionaries."""
        return [
            {
                "slug": g.slug,
                "title": g.title,
                "rating": g.rating,
                "status": g.status.value,
                "status_title": g.status_title,
                "is_liked": g.is_liked,
                "cover_url": g.cover_url,
                "game_id": g.game_id,
                "log_id": g.log_id,
                "url": g.url,
            }
            for g in self.games.values()
        ]

    def to_csv(self, file_path: str) -> None:
        """Export the user's library directly to a CSV file."""
        import csv
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Slug", "Title", "Rating", "Status", "Liked", "BackloggdURL"])
            for g in self.games.values():
                writer.writerow([
                    g.slug,
                    g.title,
                    g.rating if g.rating is not None else "",
                    g.status.value,
                    g.is_liked,
                    g.url,
                ])

    def get_stats(self) -> UserStats:
        """Compute library statistics and rating distribution."""
        rated = self.rated_games
        rated_count = len(rated)
        unrated_count = len(self) - rated_count

        avg_rating = (
            round(sum(g.rating for g in rated if g.rating is not None) / rated_count, 2)
            if rated_count > 0
            else None
        )

        dist: dict[float, int] = {}
        for g in rated:
            if g.rating is not None:
                dist[g.rating] = dist.get(g.rating, 0) + 1

        return UserStats(
            total_games=len(self),
            rated_count=rated_count,
            unrated_count=unrated_count,
            average_rating=avg_rating,
            played_count=len(self.filter(status=GameStatus.PLAYED)),
            playing_count=len(self.filter(status=GameStatus.PLAYING)),
            backlog_count=len(self.filter(status=GameStatus.BACKLOG)),
            wishlist_count=len(self.filter(status=GameStatus.WISHLIST)),
            rating_distribution=dict(sorted(dist.items())),
        )

