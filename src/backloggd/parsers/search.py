"""HTML / Turbo stream parser for Backloggd search results."""

import re
from typing import Optional
from bs4 import BeautifulSoup, NavigableString, TemplateString, Tag
from backloggd.models.game import GameSearchResult

TEXT_TYPES = (NavigableString, TemplateString)


def _text(tag: Optional[Tag], separator: str = "", strip: bool = True) -> str:
    """Extract text from tag supporting Turbo Stream templates (TemplateString)."""
    if tag is None:
        return ""
    txt = tag.get_text(separator=separator, strip=strip, types=TEXT_TYPES)
    return txt.strip() if strip else txt


def parse_game_search_results(html: str) -> list[GameSearchResult]:
    """Parse game search results from Backloggd search page or turbo stream."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    results: list[GameSearchResult] = []
    # Search items typically reside inside rows containing a .game-cover
    rows = soup.find_all(lambda tag: tag.name == "div" and "row" in tag.get("class", []) and tag.select_one(".game-cover"))

    # Fallback to direct .game-cover cards if rows aren't standard
    if not rows:
        covers = soup.select(".game-cover")
        for c in covers:
            img = c.select_one("img")
            title = img.get("alt", "").strip() if img else ""
            cover_url = img.get("src") if img else None
            game_id = c.get("game_id")
            link = c.find_parent("a", href=lambda h: bool(h and "/games/" in h)) or c.find("a", href=lambda h: bool(h and "/games/" in h))
            slug = link["href"].strip("/").split("/")[-1] if link and link.get("href") else ""
            if title and slug:
                results.append(
                    GameSearchResult(
                        title=title,
                        slug=slug,
                        cover_url=cover_url,
                        game_id=game_id,
                    )
                )
        return results

    for r in rows:
        cover = r.select_one(".game-cover")
        img = cover.select_one("img") if cover else None
        cover_url = img.get("src") if img else None
        game_id = r.get("game_id") or (cover.get("game_id") if cover else None)

        # Game link & slug
        game_link = r.select_one("a[href*='/games/']")
        if not game_link or not game_link.get("href"):
            continue

        slug = game_link["href"].strip("/").split("/")[-1]

        # Title & Subtitle (Year)
        h3 = r.select_one("h3")
        title = ""
        year: Optional[int] = None

        if h3:
            subtitle = h3.select_one(".subtitle-text, small")
            if subtitle:
                sub_text = _text(subtitle)
                match = re.search(r"(\d{4})", sub_text)
                if match:
                    year = int(match.group(1))
                # Remove year from h3 text
                title = _text(h3, separator=" ").replace(sub_text, "").strip()
            else:
                title = _text(h3)

        if not title and img and img.get("alt"):
            title = img["alt"].strip()

        if not title:
            title = slug.replace("-", " ").title()

        # Platforms
        platforms: list[str] = []
        for p_tag in r.select(".game-details-value.game-page-platform"):
            if "game-result-type" in p_tag.get("class", []):
                continue
            txt = _text(p_tag)
            if txt and txt not in platforms and not txt.startswith("+"):
                platforms.append(txt)

        # Game type (e.g. Main Game, DLC)
        type_el = r.select_one(".game-result-type")
        game_type = _text(type_el) if type_el else None

        results.append(
            GameSearchResult(
                title=title,
                slug=slug,
                release_year=year,
                cover_url=cover_url,
                game_id=game_id,
                platforms=platforms,
                game_type=game_type,
            )
        )

    return results
