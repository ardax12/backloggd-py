"""HTML parser for Backloggd games library grid."""

from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup, Tag
from backloggd.models.game import GameEntry, GameStatus

PAGE_SIZE = 70


def parse_rating(element: Tag) -> Optional[float]:
    """Extract rating from a game card element."""
    rated_el = element.find(attrs={"data-rating": True})
    if rated_el and rated_el.get("data-rating"):
        try:
            return float(rated_el["data-rating"]) / 2.0
        except (ValueError, TypeError):
            pass

    stars_top = element.select_one(".stars-top")
    if stars_top and "width:" in stars_top.get("style", ""):
        try:
            w = stars_top["style"].split("width:")[1].split("%")[0].strip()
            return float(w) / 20.0
        except (ValueError, IndexError, TypeError):
            pass

    return None


def parse_status_and_metadata(card: Tag) -> tuple[GameStatus, Optional[str], bool, Optional[str], Optional[datetime]]:
    """Extract log status, like flag, log ID, and log timestamp from preloaded log divs or quick-access buttons."""
    status = GameStatus.UNKNOWN
    status_title: Optional[str] = None
    is_liked = False
    log_id: Optional[str] = None
    logged_at: Optional[datetime] = None

    # Inspect preloaded log div
    log_div = card.find(lambda t: t.name == "div" and (t.has_attr("data-log-id") or t.has_attr("data-is-play")))
    if log_div:
        log_id = log_div.get("data-log-id")
        status_title = log_div.get("data-status-title")
        is_liked = bool(log_div.get("data-is-liked"))

        play_str = log_div.get("data-is-play")
        if play_str:
            status = GameStatus.PLAYED
            try:
                # Format: "2022-09-16 09:25:59 UTC"
                clean_str = play_str.replace(" UTC", "")
                logged_at = datetime.fromisoformat(clean_str)
            except Exception:
                pass
        elif log_div.get("data-is-playing"):
            status = GameStatus.PLAYING
        elif log_div.get("data-is-backlog"):
            status = GameStatus.BACKLOG
        elif log_div.get("data-is-wishlist"):
            status = GameStatus.WISHLIST

    # Fallback to class cues if preloaded log not present
    if status == GameStatus.UNKNOWN:
        card_classes = card.get("class", [])
        classes_str = " ".join(card_classes) if isinstance(card_classes, list) else str(card_classes)
        if "fade-played" in classes_str:
            status = GameStatus.PLAYED
        elif "fade-playing" in classes_str:
            status = GameStatus.PLAYING
        elif "fade-backlog" in classes_str:
            status = GameStatus.BACKLOG
        elif "fade-wishlist" in classes_str:
            status = GameStatus.WISHLIST

    return status, status_title, is_liked, log_id, logged_at


def parse_game_card(card: Tag) -> Optional[GameEntry]:
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
    status, status_title, is_liked, log_id, logged_at = parse_status_and_metadata(card)

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

    games: list[GameEntry] = []
    seen_slugs: set[str] = set()

    for card in cards:
        entry = parse_game_card(card)
        if entry and entry.slug not in seen_slugs:
            games.append(entry)
            seen_slugs.add(entry.slug)

    has_more = len(cards) >= PAGE_SIZE
    return games, has_more
