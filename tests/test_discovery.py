import os
import tempfile
import unittest

from agent_skills import config, discovery


class TestDiscovery(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.home = os.path.join(self.td, "home")
        os.makedirs(os.path.join(self.home, ".agents", "skills"), exist_ok=True)
        os.environ["AGENT_SKILLS_HOME"] = self.home
        # library root inside home
        self.lib = os.path.join(self.home, ".agents", "skills")
        # create skills
        for name, content in [
            ("alpha-skill", "---\nname: alpha\ndescription: alpha desc\n---\n"),
            ("beta-skill", "# no frontmatter\n"),
        ]:
            d = os.path.join(self.lib, name)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "SKILL.md"), "w") as f:
                f.write(content)
        self.cache_file = os.path.join(self.td, "cache.json")

    def tearDown(self):
        os.environ.pop("AGENT_SKILLS_HOME", None)
        os.environ.pop("AGENT_SKILLS_CONFIG", None)

    def test_discover_basic(self):
        recs, warnings, errors = discovery.discover_skills(
            library_root=self.lib,
            cache_file=self.cache_file,
            no_cache=True,
        )
        self.assertEqual(errors, [])
        names = [r["dir_name"] for r in recs]
        self.assertIn("alpha-skill", names)
        self.assertIn("beta-skill", names)
        alpha = [r for r in recs if r["dir_name"] == "alpha-skill"][0]
        self.assertEqual(alpha["frontmatter_status"], "valid")
        beta = [r for r in recs if r["dir_name"] == "beta-skill"][0]
        self.assertEqual(beta["frontmatter_status"], "missing")

    def test_cache_roundtrip(self):
        recs1, _, _ = discovery.discover_skills(library_root=self.lib, cache_file=self.cache_file)
        self.assertTrue(os.path.exists(self.cache_file))
        recs2, _, _ = discovery.discover_skills(library_root=self.lib, cache_file=self.cache_file)
        self.assertEqual(len(recs1), len(recs2))

    def test_no_cache_flag(self):
        discovery.discover_skills(library_root=self.lib, cache_file=self.cache_file)
        recs, _, _ = discovery.discover_skills(library_root=self.lib, cache_file=self.cache_file, no_cache=True)
        self.assertEqual(len(recs), 2)

    def test_missing_library(self):
        with self.assertRaises(discovery.DiscoveryError):
            discovery.discover_skills(library_root=os.path.join(self.td, "nope"), cache_file=self.cache_file, no_cache=True)

    def test_symlink_escape_rejected(self):
        # create a symlink pointing outside allowed roots
        outside = os.path.join(self.td, "outside")
        os.makedirs(outside, exist_ok=True)
        with open(os.path.join(outside, "SKILL.md"), "w") as f:
            f.write("---\nname: x\n---\n")
        link = os.path.join(self.lib, "escape-link")
        os.symlink(outside, link)
        recs, warnings, errors = discovery.discover_skills(
            library_root=self.lib, cache_file=self.cache_file, no_cache=True,
        )
        # either rejected via error or not included
        names = [r["dir_name"] for r in recs]
        self.assertNotIn("escape-link", names)

    def test_safe_id_warning(self):
        # create a dir with space in name containing SKILL.md
        d = os.path.join(self.lib, "has space")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "SKILL.md"), "w") as f:
            f.write("---\nname: x\n---\n")
        recs, warnings, errors = discovery.discover_skills(
            library_root=self.lib, cache_file=self.cache_file, no_cache=True,
        )
        self.assertTrue(any("unsafe-skill-id" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()