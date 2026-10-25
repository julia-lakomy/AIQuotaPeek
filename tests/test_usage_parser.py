import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from usage_parser import parse_usage


NOW = datetime(2026, 10, 25, 18, 0, tzinfo=ZoneInfo("Europe/Warsaw"))


class UsageParserTests(unittest.TestCase):
    def test_claude_used_becomes_remaining_and_resets_are_local(self):
        page = """Settings
Usage
Current session
Resets at 10:30 PM
88% used
Weekly limits
Resets Saturday 6:00 PM
58% used
Extra usage
99% used
"""
        result = parse_usage("claude", page, NOW)
        self.assertEqual(result["session"], {"remaining": 12, "reset": "niedziela 22:30"})
        self.assertEqual(result["weekly"], {"remaining": 42, "reset": "sobota 18:00"})

    def test_chatgpt_missing_session_is_explicitly_unavailable(self):
        page = """Użycie
Limit tygodniowy
Reset za 6 dni i 23 godz.
Pozostało 100%
"""
        result = parse_usage("chatgpt", page, NOW)
        self.assertEqual(result["session"], {"remaining": None, "reset": None})
        self.assertEqual(result["weekly"]["remaining"], 100)
        self.assertTrue(result["weekly"]["reset"].startswith("~niedziela"))

    def test_unrelated_percent_is_not_mistaken_for_a_limit(self):
        page = """Extra usage
92% used
Current session
Resets at 10:30 PM
0% used
Weekly limits
0% used
"""
        result = parse_usage("claude", page, NOW)
        self.assertEqual(result["session"]["remaining"], 100)
        self.assertEqual(result["weekly"]["remaining"], 100)

    def test_missing_headings_yield_no_values(self):
        result = parse_usage("chatgpt", "Sign in\n42% remaining", NOW)
        self.assertIsNone(result["session"]["remaining"])
        self.assertIsNone(result["weekly"]["remaining"])

    def test_concatenated_claude_labels_from_rendered_page(self):
        page = "Current sessionResets at 10:30 PM0% used\nWeekly limitsResets Saturday 6:00 PM0% used"
        result = parse_usage("claude", page, NOW)
        self.assertEqual(result["session"]["remaining"], 100)
        self.assertEqual(result["weekly"]["remaining"], 100)

    def test_chatgpt_live_english_weekly_remaining(self):
        page = "Weekly limit\nResets in 6d 23h\n96% left\n"
        result = parse_usage("chatgpt", page, NOW)
        self.assertEqual(result["weekly"]["remaining"], 96)

    def test_claude_live_usage_without_separate_weekly_heading(self):
        page = """Usage
You have 100% of your weekly limit remaining
Current session
Resets at 10:30 PM
0% used
This week
-
Resets Saturday 6:00 PM
0% used
"""
        result = parse_usage("claude", page, NOW)
        self.assertEqual(result["session"]["remaining"], 100)
        self.assertEqual(result["weekly"], {"remaining": 100, "reset": "sobota 18:00"})


if __name__ == "__main__":
    unittest.main()
