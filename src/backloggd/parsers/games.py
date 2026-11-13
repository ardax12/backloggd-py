"""HTML parser for Backloggd games library grid."""

from datetime import datetime
from typing import Optional
from urllib.parse import urlsplit
from bs4 import BeautifulSoup, Tag
from backloggd.models.game import GameEntry, GameStatus

PAGE_SIZE = 70


def parse_rating(element: Tag) -> Optional[float]:
    """Extract rating from a game card element."""
    # The visible cover holds the owner's rating; sibling preloaded logs hold
    # the viewer's rating, including when the owner has never rated the game.
    cover = element if "game-cover" in element.get("class", []) else element.select_one(".game-cover")
    scope = cover if cover is not None else element
    rated_el = scope if scope.has_attr("data-rating") else scope.find(attrs={"data-rating": True})
    if rated_el and (
        rated_el.has_attr("data-log-id")
        or rated_el.find_parent(id=lambda value: bool(value and value.startswith("preloaded-log-")))
    ):
        rated_el = None
    if rated_el and rated_el.get("data-rating"):
        try:
            return float(rated_el["data-rating"]) / 2.0
        except (ValueError, TypeError):
            pass

    stars_top = scope.select_one(".stars-top")
    if stars_top and "width:" in stars_top.get("style", ""):
        try:
            w = stars_top["style"].split("width:")[1].split("%")[0].strip()
            return float(w) / 20.0
        except (ValueError, IndexError, TypeError):
            pass

    return None


def _owner_collection_status(soup: BeautifulSoup) -> GameStatus:
    """Read the profile owner's collection, not the viewer's quick-edit state."""
    statuses = set()
    for marker in soup.select('[data-controller~="game-filters"][data-game-filters-base-url-value]'):
        path = urlsplit(marker["data-game-filters-base-url-value"]).path.strip("/").split("/")
        if len(path) < 4 or path[0] != "u" or path[2] != "games":
            continue
        preset = marker.get("data-game-filters-preset-value")
        if preset != path[3] or preset not in {"played", "playing", "backlog", "wishlist"}:
            return GameStatus.UNKNOWN
        statuses.add(GameStatus(preset))
    return next(iter(statuses)) if len(statuses) == 1 else GameStatus.UNKNOWN


def parse_status_and_metadata(
    card: Tag, *, owner_status: GameStatus = GameStatus.UNKNOWN,
) -> tuple[GameStatus, Optional[str], bool, Optional[str], Optional[datetime]]:
    """Use validated owner collection context; absent owner metadata stays empty.

    Preloaded logs, quick-access buttons, and fade classes describe the logged-in
    viewer. They cannot establish the owner's completion label, like, or log ID.
    """
    return owner_status, None, False, None, None


def parse_game_card(card: Tag, *, owner_status: GameStatus = GameStatus.UNKNOWN) -> Optional[GameEntry]:
    """Parse a single game card into a GameEntry model."""
    link = card.select_one("a.cover-link")
    if not link:
        link = card.find("a", href=lambda h: bool(h and "/games/" in h))

    if not link or not link.get("href"):
        return None

    slug = link["href"].strip("/").split("/")[-1]
    if not slug or slug in ("popular", "games", "lib"):
        return None

    # Title extraction
    title_el = card.select_one(".game-text-centered")
    img_el = card.select_one("img")
    title = ""
    if title_el and title_el.get_text(strip=True):
        title = title_el.get_text(strip=True)
    elif img_el and img_el.get("alt"):
        title = img_el["alt"].strip()
    else:
        title = slug.replace("-", " ").title()

    cover_url = img_el.get("src") if img_el else None

    # Game ID
    game_cover = card.select_one(".game-cover") or card
    game_id = game_cover.get("game_id")

    rating = parse_rating(card)
    status, status_title, is_liked, log_id, logged_at = parse_status_and_metadata(card, owner_status=owner_status)

    return GameEntry(
        slug=slug,
        title=title,
        rating=rating,
        status=status,
        status_title=status_title,
        is_liked=is_liked,
        cover_url=cover_url,
        game_id=game_id,
        log_id=log_id,
        logged_at=logged_at,
    )


def parse_games_page(html: str) -> tuple[list[GameEntry], bool]:
    """Parse a page of game cards from HTML.

    Returns:
        tuple[list[GameEntry], bool]: (games_list, has_more_pages)
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".col-cus-user-games:not(:has(.empty-card)), .col-cus-5:not(:has(.empty-card))")
    if not cards:
        cards = soup.select(".rating-hover")

    owner_status = _owner_collection_status(soup)
    games: list[GameEntry] = []
    seen_slugs: set[str] = set()

    for card in cards:
        entry = parse_game_card(card, owner_status=owner_status)
        if entry and entry.slug not in seen_slugs:
            games.append(entry)
            seen_slugs.add(entry.slug)

    has_more = len(cards) >= PAGE_SIZE
    return games, has_more
