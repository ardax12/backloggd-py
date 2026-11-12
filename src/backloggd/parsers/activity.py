"""HTML parsing and validation for Backloggd user activity pages."""
import hashlib
import re
from bs4 import BeautifulSoup
from typing import Optional
from backloggd.models.activity import ActivityEntry
from backloggd.utils import clean_image_url
from backloggd.exceptions import PageParseError


def validate_activity_page(html: str) -> None:
    """A challenge or unknown layout must never initialize an empty feed."""
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one("#activities-list"):
        raise PageParseError("Activity page is blocked or has an unrecognized layout")


def parse_user_activity_page(html: str, username: str) -> list[ActivityEntry]:
    """Parse Backloggd user activity page HTML and return only genuine game activities.
    
    Ignores non-game activities like badges, user follows, and likes.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Target activity stream rows or cards
    rows = soup.select("#activities-list .row.activity, .row.activity")
    if not rows:
        rows = soup.select(".activity-row, .stream-entry, .stream-row, .feed-item")

    activities: list[ActivityEntry] = []
    seen_ids: set[str] = set()

    # Keep the innermost event container, excluding layout wrappers.
    row_ids = {id(row) for row in rows}
    rows = [row for row in rows if not any(id(child) in row_ids for child in row.find_all(True))]

    for row in rows:
        # 1. STRICT GAME OBJECT FILTER: Must contain a link to /games/{slug}/
        # This completely filters out badges (/badges/), users (/u/), follows, etc.
        game_link = row.find("a", href=lambda h: bool(h and "/games/" in h and not any(k in h for k in ["/popular", "/trending"])))
        if not game_link or not game_link.get("href"):
            continue

        raw_href = game_link["href"].strip("/")
        parts = raw_href.split("/")
        if "games" not in parts:
            continue
        slug_idx = parts.index("games") + 1
        if slug_idx >= len(parts):
            continue
        game_slug = parts[slug_idx]
        if not game_slug or game_slug in ("popular", "games", "lib"):
            continue

        # Extract Game Title
        game_title = game_link.get_text(strip=True)
        img = row.select_one(".game-cover img") or row.find("img")
        if not game_title and img and img.get("alt"):
            game_title = img["alt"].strip()
        if not game_title:
            title_el = row.select_one(".game-text-centered, .game-title, h3, h4")
            if title_el:
                game_title = title_el.get_text(strip=True)
        if not game_title:
            game_title = game_slug.replace("-", " ").title()

        cover_url = clean_image_url(img.get("src") if img else None)

        # 2. Extract Rating if present
        rating: Optional[float] = None
        rated_el = row.find(attrs={"data-rating": True})
        if rated_el and rated_el.get("data-rating"):
            try:
                rating = float(rated_el["data-rating"]) / 2.0
            except (ValueError, TypeError):
                pass
        if rating is None:
            stars_top = row.select_one(".stars-top")
            if stars_top and "width:" in stars_top.get("style", ""):
                try:
                    w = stars_top["style"].split("width:")[1].split("%")[0].strip()
                    rating = float(w) / 20.0
                except (ValueError, IndexError, TypeError):
                    pass

        # 3. Detect Action Type & Action Text
        headline = row.select_one("a.game-title")
        headline = headline.parent if headline else row
        # Remove names, titles, timestamps and review prose before classifying.
        headline_copy = BeautifulSoup(str(headline), "html.parser")
        for element in headline_copy.select("a, img, .stars-top, .stars-bottom, time, .time-ago, .review-text, .card-text, .body-text, .review-body"):
            element.decompose()
        row_text = headline_copy.get_text(" ", strip=True).lower()
        action_type = "unknown"
        action_text = "updated"
        if re.search(r"\b(liked|likes|commented|followed|badge|list)\b", row_text):
            continue
        if re.search(r"\b(completed|finished)\b", row_text):
            action_type, action_text = "completed", "completed"
        elif re.search(r"\b(playing|started)\b", row_text):
            action_type, action_text = "playing", "started playing"
        elif re.search(r"\breview(?:ed)?\b", row_text) or row.select_one(".review-text, .review-body"):
            action_type, action_text = "reviewed", "reviewed"
        elif "backlog" in row_text:
            action_type, action_text = "backlog", "added to backlog"
        elif "wishlist" in row_text or "wishlisted" in row_text:
            action_type, action_text = "wishlist", "wishlisted"
        elif re.search(r"\b(replayed|replaying)\b", row_text):
            action_type, action_text = "replay", "replayed"
        elif re.search(r"\b(rated|rating|rerated|re-rated)\b", row_text):
            action_type, action_text = "rated", "rated"
        elif re.search(r"\bplayed\b", row_text):
            action_type, action_text = "played", "played"

        # 4. Review text or notes if user wrote thoughts
        review_notes = None
        body_div = row.select_one(".review-text, .card-text, .body-text, .review-body")
        if body_div:
            review_notes = body_div.get_text(separator=" ", strip=True)

        # Backloggd embeds its machine-readable time inside a tooltip HTML string.
        time_el = row.select_one("time, .time-tooltip, .time-ago, .date, [datetime], [data-timestamp]")
        date_str = time_el.get_text(strip=True) if time_el else None
        timestamp = (time_el.get("datetime") or time_el.get("data-timestamp")) if time_el else None
        if time_el and not timestamp:
            tooltip = BeautifulSoup(time_el.get("data-tippy-content", ""), "html.parser")
            tooltip_time = tooltip.select_one("time[datetime]")
            if tooltip_time:
                timestamp = tooltip_time["datetime"]
        permalink = row.find("a", href=re.compile(r"/(?:review|logs?)/\d+(?:/|$)"))
        reference = permalink.get("href") if permalink else None
        raw_id = row.get("data-activity-id") or row.get("data-log-id") or row.get("id")
        # Namespace server-side IDs by user; timestamped identity excludes mutable
        # rating/review content so subsequent polls can update the same message.
        identity = raw_id or reference or timestamp
        if not identity:
            identity = f"{rating}:{review_notes or ''}"
        hash_input = f"{username.lower()}:{game_slug}:{action_type}:{identity}"
        act_id = "act_" + hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:24]

        if act_id in seen_ids:
            continue
        seen_ids.add(act_id)

        activities.append(
            ActivityEntry(
                activity_id=act_id,
                game_title=game_title,
                game_slug=game_slug,
                cover_url=cover_url,
                action_type=action_type,
                action_text=action_text,
                rating=rating,
                review_notes=review_notes,
                date_str=date_str,
                occurred_at=timestamp,
                reference=reference,
                is_replay=action_type == "replay" or bool(re.search(r"\breplay(?:ed|ing)?\b", row_text)),
                has_spoilers=bool(row.select_one(".spoiler, .has-spoilers, [class*=spoiler]")),
            )
        )

    return activities
