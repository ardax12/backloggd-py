"""HTML parser for Backloggd playthrough journal pages."""

import re
from typing import Optional
from bs4 import BeautifulSoup
from backloggd.models.journal import JournalEntry
from backloggd.exceptions import PageParseError


def parse_journal_page(html: str) -> tuple[list[JournalEntry], bool]:
    """Parse a user's journal page into a list of JournalEntry models.

    Returns:
        tuple[list[JournalEntry], bool]: (entries_list, has_more_pages)
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    entries: list[JournalEntry] = []

    # Journal layout organizes by Month/Year, Day, and game rows
    current_month_year = ""
    current_day = ""

    # Look for game rows with covers
    covers = soup.select("h4, h5, .game-cover")
    month_pattern = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4}$")
    for cover in covers:
        if cover.name in ("h4", "h5"):
            text = cover.get_text(strip=True)
            if month_pattern.fullmatch(text):
                current_month_year, current_day = text, ""
            elif text.isdigit() and 1 <= int(text) <= 31:
                current_day = text
            continue
        img = cover.select_one("img")
        cover_url = img.get("src") if img else None
        game_id = cover.get("game_id")

        # Find enclosing row
        row = cover.find_parent("div", class_="row")
        if not row:
            continue

        # Game title and slug
        game_a = row.select_one(".game-name a, a[href*='/games/']")
        if not game_a or not game_a.get("href"):
            continue

        game_title = game_a.get_text(strip=True) or (img.get("alt", "").strip() if img else "")
        slug = game_a["href"].strip("/").split("/")[-1]

        # Rating from stars-top width
        rating: Optional[float] = None
        stars_top = row.select_one(".stars-top")
        if stars_top and "width:" in stars_top.get("style", ""):
            try:
                w = stars_top["style"].split("width:")[1].split("%")[0].strip()
                rating = float(w) / 20.0
            except (ValueError, IndexError):
                pass

        # Replay badge or indicator
        is_replay = bool(row.select_one(".replay, [class*='replay'], .fa-rotate-right, .fa-repeat"))

        played_date = f"{current_month_year} {current_day}".strip() if current_month_year else None
        labels = tuple(dict.fromkeys(
            label.get_text(strip=True) for label in row.select(".journal-time")
            if label.get_text(strip=True) in ("Started", "Finished")
        ))
        platform_tag = row.select_one(".journal-platform") or row.select_one(".col-3 p")
        platform = platform_tag.get_text(strip=True) if platform_tag else None
        if platform == "-":
            platform = None

        entry_id = game_id or slug

        entries.append(
            JournalEntry(
                entry_id=entry_id,
                game_title=game_title,
                game_slug=slug,
                played_date=played_date,
                rating=rating,
                is_replay=is_replay,
                cover_url=cover_url,
                platform=platform,
                session_labels=labels,
            )
        )

    # Check for next page
    next_btn = soup.find("a", rel=lambda r: bool(r and "next" in r)) or soup.find("a", string=lambda s: bool(s and "Next" in s))
    has_more = bool(next_btn)

    return entries, has_more


def validate_journal_page(html: str) -> None:
    """Accept journal sections or recognized empty pages, never challenge HTML."""
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one(".journal_entry, .game-cover"):
        return
    if soup.select_one("main") and soup.title and "journal" in soup.title.get_text().lower():
        return
    raise PageParseError("Journal page is blocked or has an unrecognized layout")
