"""Tests for the summarise runner's handling of names and report markers written by older versions."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class SummarizeTest(unittest.TestCase):
    def test_course_name_strips_en_dash_code(self):
        from halmem.summarize import clean_course_name

        self.assertEqual(clean_course_name("Algorithms \u2013 COM1234"), "Algorithms")

    def test_course_name_strips_hyphen_code(self):
        from halmem.summarize import clean_course_name

        self.assertEqual(clean_course_name("Algorithms - COM1234"), "Algorithms")

    def test_gap_marks_match_old_and_new_report_rows(self):
        from halmem.summarize import GAP_MARKS

        old = "\u274c none \u2014 needs summary"
        new = "none - needs summary"
        self.assertTrue(all(any(m in row for m in GAP_MARKS) for row in (old, new)))
        self.assertFalse(any(m in "yes: Week 1 notes" for m in GAP_MARKS))

    def test_maybe_marks_match_old_and_new_report_rows(self):
        from halmem.summarize import MAYBE_MARKS

        old = "\U0001f7e1 maybe: Course structure.md"
        new = "maybe: Course structure.md"
        self.assertTrue(all(any(m in row for m in MAYBE_MARKS) for row in (old, new)))


if __name__ == "__main__":
    unittest.main()
