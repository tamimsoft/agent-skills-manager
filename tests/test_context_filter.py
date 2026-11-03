import os
import tempfile
import unittest

from agent_skills import config
from agent_skills.recommend import filter_skills_for_context


def _make_skill(lib_root, dir_name, content):
    d = os.path.join(lib_root, dir_name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w") as f:
        f.write(content)
    return d


class TestContextFilter(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.home = os.path.join(self.td, "home")
        os.makedirs(os.path.join(self.home, ".agents", "skills"), exist_ok=True)
        os.environ["AGENT_SKILLS_HOME"] = self.home
        self.lib = os.path.join(self.home, ".agents", "skills")
        # Create skills with varying content sizes.
        self.skills = {}
        for name, content in [
            ("alpha-skill", "---\nname: alpha\ndescription: alpha desc\n---\nshort"),
            ("beta-skill", "---\nname: beta\ndescription: beta desc\n---\n" + "x" * 1000),
            ("gamma-skill", "---\nname: gamma\ndescription: gamma desc\n---\n" + "y" * 5000),
            ("delta-skill", "---\nname: delta\ndescription: delta desc\n---\n" + "z" * 20000),
        ]:
            self.skills[name] = _make_skill(self.lib, name, content)

    def tearDown(self):
        os.environ.pop("AGENT_SKILLS_HOME", None)
        os.environ.pop("AGENT_SKILLS_CONFIG", None)

    def _records(self, names):
        """Build skill record dicts from dir names."""
        cfg, _ = config.load_config()
        from agent_skills.discovery import discover_skills
        records, _, _ = discover_skills(
            library_root=self.lib,
            cache_file=os.path.join(self.td, "cache.json"),
            no_cache=True,
        )
        rec_map = {r["dir_name"]: r for r in records}
        return [rec_map[n] for n in names if n in rec_map]

    def test_filter_by_selected_ids(self):
        records = self._records(["alpha-skill", "beta-skill", "gamma-skill"])
        filtered, skipped, total, warnings = filter_skills_for_context(
            records, ["alpha-skill", "beta-skill"], [], None, 10,
        )
        names = [r["dir_name"] for r in filtered]
        self.assertEqual(names, ["alpha-skill", "beta-skill"])
        self.assertEqual(skipped, 0)

    def test_unselected_skill_excluded(self):
        records = self._records(["alpha-skill", "beta-skill"])
        filtered, skipped, total, warnings = filter_skills_for_context(
            records, ["alpha-skill"], [], None, 10,
        )
        names = [r["dir_name"] for r in filtered]
        self.assertEqual(names, ["alpha-skill"])
        self.assertEqual(skipped, 0)
        self.assertEqual(len(filtered), 1)

    def test_token_budget_truncation(self):
        records = self._records(["alpha-skill", "beta-skill", "gamma-skill", "delta-skill"])
        # Very small budget: only alpha fits.
        filtered, skipped, total, warnings = filter_skills_for_context(
            records, ["alpha-skill", "beta-skill", "gamma-skill", "delta-skill"],
            [], 100, 10,
        )
        names = [r["dir_name"] for r in filtered]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(names[0], "alpha-skill")
        self.assertEqual(skipped, 3)
        self.assertTrue(any("context budget" in w for w in warnings))

    def test_max_skills_truncation(self):
        records = self._records(["alpha-skill", "beta-skill", "gamma-skill", "delta-skill"])
        filtered, skipped, total, warnings = filter_skills_for_context(
            records, ["alpha-skill", "beta-skill", "gamma-skill", "delta-skill"],
            [], None, 2,
        )
        names = [r["dir_name"] for r in filtered]
        self.assertEqual(len(filtered), 2)
        self.assertEqual(skipped, 2)

    def test_scoring_order(self):
        # With no technologies, all score 0; sorted by dir_name asc.
        records = self._records(["delta-skill", "alpha-skill", "gamma-skill"])
        filtered, skipped, total, warnings = filter_skills_for_context(
            records, ["delta-skill", "alpha-skill", "gamma-skill"], [], None, 10,
        )
        names = [r["dir_name"] for r in filtered]
        self.assertEqual(names, ["alpha-skill", "delta-skill", "gamma-skill"])

    def test_unlimited_budget_none(self):
        records = self._records(["alpha-skill", "beta-skill", "gamma-skill"])
        filtered, skipped, total, warnings = filter_skills_for_context(
            records, ["alpha-skill", "beta-skill", "gamma-skill"], [], None, 10,
        )
        self.assertEqual(len(filtered), 3)
        self.assertEqual(skipped, 0)

    def test_unlimited_budget_zero(self):
        records = self._records(["alpha-skill", "beta-skill"])
        filtered, skipped, total, warnings = filter_skills_for_context(
            records, ["alpha-skill", "beta-skill"], [], 0, 10,
        )
        # budget_tokens=0 means unlimited.
        self.assertEqual(len(filtered), 2)
        self.assertEqual(skipped, 0)

    def test_empty_selection(self):
        records = self._records(["alpha-skill"])
        filtered, skipped, total, warnings = filter_skills_for_context(
            records, [], [], 32768, 50,
        )
        self.assertEqual(filtered, [])
        self.assertEqual(skipped, 0)
        self.assertEqual(total, 0)

    def test_unlimited_max_skills_zero(self):
        """max_skills_in_context=0 means unlimited, not zero skills."""
        records = self._records(["alpha-skill", "beta-skill", "gamma-skill"])
        filtered, skipped, total, warnings = filter_skills_for_context(
            records, ["alpha-skill", "beta-skill", "gamma-skill"], [], None, 0,
        )
        names = [r["dir_name"] for r in filtered]
        self.assertEqual(len(filtered), 3)
        self.assertEqual(names, ["alpha-skill", "beta-skill", "gamma-skill"])
        self.assertEqual(skipped, 0)

    def test_unknown_selected_id_not_counted_as_skipped(self):
        """Undiscovered/nonexistent selected skills should not inflate skipped count."""
        records = self._records(["alpha-skill"])
        filtered, skipped, total, warnings = filter_skills_for_context(
            records, ["alpha-skill", "nonexistent-skill"], [], 32768, 50,
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["dir_name"], "alpha-skill")
        # nonexistent-skill was never a candidate, so skipped must be 0.
        self.assertEqual(skipped, 0)


if __name__ == "__main__":
    unittest.main()
