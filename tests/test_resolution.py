import os
import tempfile
import unittest

from agent_skills import discovery, resolution


class TestResolution(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.home = os.path.join(self.td, "home")
        os.makedirs(os.path.join(self.home, ".agents", "skills"), exist_ok=True)
        self.lib = os.path.join(self.home, ".agents", "skills")

        def make_skill(name, frontmatter):
            d = os.path.join(self.lib, name)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "SKILL.md"), "w") as f:
                f.write(frontmatter)

        # Valid skill with declared name matching folder.
        make_skill("alpha-skill", "---\nname: alpha\ndescription: a\n---\n")
        # Skill with declared name different from folder.
        make_skill("beta-skill", "---\nname: beta-alias\ndescription: b\n---\n")
        # No frontmatter.
        d = os.path.join(self.lib, "nofm-skill")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "SKILL.md"), "w") as f:
            f.write("# no frontmatter\n")
        # Two skills with same declared name (collision).
        make_skill("collision-a", "---\nname: shared\ndescription: x\n---\n")
        make_skill("collision-b", "---\nname: shared\ndescription: y\n---\n")

    def _discover(self):
        recs, _, _ = discovery.discover_skills(
            library_root=self.lib, no_cache=True, cache_file=None,
        )
        return {r["dir_name"]: r for r in recs}

    def test_available(self):
        rec_map = self._discover()
        res = resolution.resolve_resolutions(
            list(rec_map.values()), ["alpha-skill"], ["kilo"],
        )
        state, reason = res["alpha-skill"]["kilo"]
        self.assertEqual(state, resolution.AVAILABLE)

    def test_unavailable_no_frontmatter_opencode(self):
        rec_map = self._discover()
        res = resolution.resolve_resolutions(
            list(rec_map.values()), ["nofm-skill"], ["opencode"],
        )
        state, reason = res["nofm-skill"]["opencode"]
        self.assertEqual(state, resolution.UNAVAILABLE)

    def test_conflict_declared_name_kilo(self):
        rec_map = self._discover()
        res = resolution.resolve_resolutions(
            list(rec_map.values()), ["collision-a", "collision-b"], ["kilo"],
        )
        # Both collide on declared_name "shared" for kilo.
        state_a, _ = res["collision-a"]["kilo"]
        state_b, _ = res["collision-b"]["kilo"]
        self.assertEqual(state_a, resolution.CONFLICT)
        self.assertEqual(state_b, resolution.CONFLICT)

    def test_unresolved_unsafe_id(self):
        # Create a skill with an unsafe folder name (space). OpenCode uses
        # dir_name as agent_id, so this should be unresolved.
        d = os.path.join(self.lib, "bad name")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "SKILL.md"), "w") as f:
            f.write("---\nname: x\ndescription: y\n---\n")
        rec_map = self._discover()
        res = resolution.resolve_resolutions(
            list(rec_map.values()), ["bad name"], ["opencode"],
        )
        state, reason = res["bad name"]["opencode"]
        self.assertEqual(state, resolution.UNRESOLVED)

    def test_missing_skill(self):
        rec_map = self._discover()
        res = resolution.resolve_resolutions(
            list(rec_map.values()), ["nonexistent"], ["kilo"],
        )
        state, reason = res["nonexistent"]["kilo"]
        self.assertEqual(state, resolution.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
