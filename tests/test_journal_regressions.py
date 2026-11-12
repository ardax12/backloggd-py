import os
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
from pathlib import Path
import unittest
import backloggd.client
from backloggd.parsers.journal import parse_journal_page

HTML = (Path(__file__).parent / "fixtures" / "ardax12_journal.html").read_text(encoding="utf-8")

class JournalDateTests(unittest.TestCase):
    def test_actual_journal_dates(self):
        entries, _ = parse_journal_page(HTML)
        self.assertEqual([(e.game_slug, e.played_date) for e in entries], [
            ("life-is-strange", "March, 2026 20"),
            ("silent-hill-2", "February, 2026 11"),
            ("a-way-out", "January, 2026 20"),
            ("omori", "January, 2026 16"),
            ("catherine", "January, 2026 05"),
            ("dispatch--3", "November, 2025 22"),
        ])

    def test_client_uses_corrected_parser(self):
        entries, _ = backloggd.client.parse_journal_page(HTML)
        self.assertEqual(next(e.played_date for e in entries if e.game_slug == "catherine"), "January, 2026 05")

    def test_month_without_day_does_not_inherit_previous_month(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(HTML, "html.parser")
        soup.select(".date-day")[1].decompose()
        entries, _ = parse_journal_page(str(soup))
        self.assertEqual(entries[1].played_date, "February, 2026")

    def test_metadata_and_pagination_are_preserved(self):
        entries, more = parse_journal_page(HTML + '<a rel="next" href="?page=2">Next</a>')
        self.assertTrue(more)
        self.assertEqual(entries[0].rating, 3.5)
        self.assertEqual(entries[0].entry_id, "7599")
        self.assertTrue(entries[0].cover_url.endswith("co1r8e.jpg"))


    def test_platform_is_preserved_from_actual_journal(self):
        entries, _ = parse_journal_page(HTML)
        self.assertEqual(next(e.platform for e in entries if e.game_slug == "catherine"), "PlayStation 3")
