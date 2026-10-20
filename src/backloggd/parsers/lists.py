"""HTML parser for Backloggd custom user lists."""

from typing import Optional
from bs4 import BeautifulSoup
from backloggd.models.game import GameEntry
from backloggd.models.list import UserList, UserListSummary


def parse_user_lists_overview(html: str, author: str) -> list[UserListSummary]:
    """Parse list summaries from /u/<username>/lists/ page."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    summaries: list[UserListSummary] = []
    # Find links to user lists
    for a in soup.find_all("a", href=lambda h: bool(h and f"/u/{author}/list" in h)):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if not title or title == author or href.endswith("/lists/"):
            continue

        slug = href.strip("/").split("/")[-1]
        full_url = f"https://backloggd.com{href}" if href.startswith("/") else href

        summaries.append(
            UserListSummary(
                title=title,
                slug=slug,
                author=author,
                url=full_url,
            )
        )

    # De-duplicate by URL while preserving order
    unique_summaries: list[UserListSummary] = []
    seen: set[str] = set()
    for s in summaries:
        if s.url not in seen:
            unique_summaries.append(s)
            seen.add(s.url)

    return unique_summaries


def parse_single_list_page(html: str, url: str) -> UserList:
    """Parse a full list page into a UserList model."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Author
    author = ""
    author_a = soup.find("a", href=lambda h: bool(h and "/u/" in h and "/list" not in h))
    if author_a:
        author = author_a.get_text(strip=True)

    # List title
    title = url.strip("/").split("/")[-1].replace("-", " ").title()
    title_el = soup.select_one("#list-title, .list-title, h1, h2")
    if title_el and title_el.get_text(strip=True) and title_el.get_text(strip=True) != "Log a Game":
        title = title_el.get_text(strip=True)

    slug = url.strip("/").split("/")[-1]

    # Description
    desc_el = soup.select_one(".list-description, #list-description, .description")
    description = desc_el.get_text(strip=True) if desc_el else None

    # Parse game cards in list
    games: list[GameEntry] = []
    covers = soup.select(".game-cover")

    for c in covers:
        img = c.select_one("img")
        game_title = img.get("alt", "").strip() if img else ""
        cover_url = img.get("src") if img else None
        game_id = c.get("game_id")

        # Game slug from parent or sibling link if available
        link = c.find_parent("a", href=lambda h: bool(h and "/games/" in h)) or c.find("a", href=lambda h: bool(h and "/games/" in h))
        if not link:
            parent_a = c.find_parent("a")
            if parent_a and parent_a.get("href"):
                link = parent_a

        game_slug = ""
        if link and link.get("href"):
            game_slug = link["href"].strip("/").split("/")[-1]
        elif game_title:
            game_slug = game_title.lower().replace(" ", "-").replace(":", "").replace("'", "")

        if game_title:
            games.append(
                GameEntry(
                    slug=game_slug,
                    title=game_title,
                    cover_url=cover_url,
                    game_id=game_id,
                )
            )

    return UserList(
        title=title,
        slug=slug,
        author=author,
        url=url,
        description=description,
        games=games,
    )
