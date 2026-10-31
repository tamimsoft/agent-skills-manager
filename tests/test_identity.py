import unittest

from agent_skills.identity import (
    is_safe_id,
    make_skill_record,
    check_duplicate_declared_names,
    check_name_folder_mismatch,
)


class TestIdentity(unittest.TestCase):
    def test_safe_id(self):
        self.assertTrue(is_safe_id("flutter-tamim"))
        self.assertTrue(is_safe_id("agent.development"))
        self.assertFalse(is_safe_id("../evil"))
        self.assertFalse(is_safe_id("has/slash"))
        self.assertFalse(is_safe_id(".hidden"))
        self.assertFalse(is_safe_id(""))
        self.assertFalse(is_safe_id("has space"))

    def test_make_skill_record_missing_frontmatter(self):
        fm = {"status": "missing", "data": {}, "warnings": [], "error": None}
        rec = make_skill_record("flutter-tamim", "/tmp/x", False, fm)
        self.assertEqual(rec["dir_name"], "flutter-tamim")
        self.assertIsNone(rec["declared_name"])
        self.assertEqual(rec["frontmatter_status"], "missing")

    def test_make_skill_record_with_override(self):
        fm = {"status": "missing", "data": {}, "warnings": [], "error": None}
        rec = make_skill_record("flutter-tamim", "/tmp/x", False, fm, overrides={
            "flutter-tamim": {"name": "flutter-tamim", "description": "Flutter skill"}
        })
        self.assertEqual(rec["declared_name"], "flutter-tamim")
        self.assertEqual(rec["description"], "Flutter skill")

    def test_duplicate_declared_names(self):
        r1 = {"dir_name": "a", "declared_name": "same", "frontmatter_status": "valid"}
        r2 = {"dir_name": "b", "declared_name": "same", "frontmatter_status": "valid"}
        dups = check_duplicate_declared_names([r1, r2])
        self.assertEqual(len(dups), 1)

    def test_name_folder_mismatch(self):
        r = {"dir_name": "foo", "declared_name": "Bar", "frontmatter_status": "valid"}
        mm = check_name_folder_mismatch([r])
        self.assertEqual(mm, [("foo", "Bar")])


if __name__ == "__main__":
    unittest.main()