from pathlib import Path
import unittest
from backloggd.parsers.activity import parse_user_activity_page, validate_activity_page
from backloggd.parsers.journal import parse_journal_page as patched_parse_journal_page
from backloggd import PageParseError
FIXTURES = Path(__file__).parent / "fixtures"
ACTIVITY = (FIXTURES / "millers_activity.html").read_text(encoding="utf-8")
JOURNAL = (FIXTURES / "millers_journal.html").read_text(encoding="utf-8")

class ActivityJournalTests(unittest.TestCase):
    def test_millers_completion_uses_exact_time_and_game_cover(self):
        events = parse_user_activity_page(ACTIVITY, "Millers")
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.action_type, "completed")
        self.assertEqual(event.rating, 3.0)
        self.assertEqual(event.occurred_at, "2026-11-11T15:48:38Z")
        self.assertTrue(event.cover_url.endswith("co2lbb.jpg"))

    def test_tooltip_time_distinguishes_new_events_but_display_time_does_not(self):
        first = parse_user_activity_page(ACTIVITY, "Millers")[0]
        later_display = parse_user_activity_page(ACTIVITY.replace("10:48", "11:48"), "Millers")[0]
        new_event = parse_user_activity_page(ACTIVITY.replace("2026-11-11T15:48:38Z", "2026-11-12T15:48:38Z"), "Millers")[0]
        self.assertEqual(first.activity_id, later_display.activity_id)
        self.assertNotEqual(first.activity_id, new_event.activity_id)

    def test_journal_preserves_milestones_and_same_day_rows(self):
        entries, _ = patched_parse_journal_page(JOURNAL)
        self.assertEqual(entries[0].session_labels, ("Finished",))
        self.assertEqual(entries[1].session_labels, ("Started",))
        self.assertEqual(len(entries), 30)
        self.assertEqual(entries[0].played_date, "November, 2026 11")
        self.assertEqual(entries[1].played_date, "November, 2026 05")

    def test_blocked_and_unknown_pages_are_not_empty_successes(self):
        from backloggd.parsers.activity import validate_activity_page
        with self.assertRaises(PageParseError):
            validate_activity_page('<title>Making sure you are not a bot!</title>')
        with self.assertRaises(PageParseError):
            validate_activity_page('<html>unexpected markup</html>')
        validate_activity_page('<div id="activities-list">No recent activity</div>')

    def test_action_words_in_game_title_do_not_classify_event(self):
        html = ACTIVITY.replace("Grand Theft Auto: Vice City", "Backlog Review Playing")
        self.assertEqual(parse_user_activity_page(html, "Millers")[0].action_type, "completed")

    def test_explicit_rating_action_and_social_actions(self):
        rating_html = ACTIVITY.replace("finished", "rated")
        self.assertEqual(parse_user_activity_page(rating_html, "Millers")[0].action_type, "rated")
        self.assertEqual(parse_user_activity_page(ACTIVITY.replace("finished", "liked a review of"), "Millers"), [])


class ParserTests(unittest.TestCase):
    def test_relative_time_does_not_change_identity(self):
        html = '<div class="stream-entry"><a href="/games/hades/">Hades</a> completed <span class="time-ago">{}</span></div>'
        first = parse_user_activity_page(html.format("1 hour ago"), "Tester")[0]
        later = parse_user_activity_page(html.format("2 hours ago"), "Tester")[0]
        self.assertEqual(first.activity_id, later.activity_id)

    def test_nested_containers_only_emit_leaf_event(self):
        html = '<div class="col-12"><div class="stream-entry" data-activity-id="123"><a href="/games/hades/">Hades</a> completed</div></div>'
        self.assertEqual(len(parse_user_activity_page(html, "Tester")), 1)

    def test_absolute_times_distinguish_repeated_events(self):
        html = '<div class="stream-entry"><a href="/games/hades/">Hades</a> completed <time datetime="{}">yesterday</time></div>'
        a = parse_user_activity_page(html.format("2026-01-01"), "Tester")[0]
        b = parse_user_activity_page(html.format("2026-01-02"), "Tester")[0]
        self.assertNotEqual(a.activity_id, b.activity_id)
