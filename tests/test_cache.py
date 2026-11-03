import os
import tempfile
import unittest

from agent_skills import cache


class TestCache(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.td, "cache.json")

    def _make_cache(self, library_root, skills, schema_version=cache.CACHE_SCHEMA_VERSION,
                    overrides_version=cache.OVERRIDES_VERSION):
        cache.save_cache(self.cache_file, {
            "library_root": str(os.path.realpath(library_root)),
            "schema_version": schema_version,
            "overrides_version": overrides_version,
            "skills": skills,
        })

    def test_valid_cache_hit(self):
        lib = os.path.join(self.td, "lib")
        os.makedirs(lib)
        sm = os.path.join(lib, "SKILL.md")
        with open(sm, "w") as f:
            f.write("hello")
        key = cache.cache_key_for_skill(sm)
        self._make_cache(lib, {"alpha-skill": {"key": key}})
        entries = [("alpha-skill", sm)]
        self.assertTrue(cache.is_cache_valid(
            cache.load_cache(self.cache_file), lib, entries, cache.OVERRIDES_VERSION))

    def test_schema_version_mismatch_invalidates(self):
        lib = os.path.join(self.td, "lib")
        os.makedirs(lib)
        sm = os.path.join(lib, "SKILL.md")
        with open(sm, "w") as f:
            f.write("hello")
        key = cache.cache_key_for_skill(sm)
        self._make_cache(lib, {"alpha-skill": {"key": key}}, schema_version=99)
        entries = [("alpha-skill", sm)]
        self.assertFalse(cache.is_cache_valid(
            cache.load_cache(self.cache_file), lib, entries, cache.OVERRIDES_VERSION))

    def test_overrides_version_mismatch_invalidates(self):
        lib = os.path.join(self.td, "lib")
        os.makedirs(lib)
        sm = os.path.join(lib, "SKILL.md")
        with open(sm, "w") as f:
            f.write("hello")
        key = cache.cache_key_for_skill(sm)
        self._make_cache(lib, {"alpha-skill": {"key": key}}, overrides_version=99)
        entries = [("alpha-skill", sm)]
        self.assertFalse(cache.is_cache_valid(
            cache.load_cache(self.cache_file), lib, entries, cache.OVERRIDES_VERSION))

    def test_content_change_detected(self):
        lib = os.path.join(self.td, "lib")
        os.makedirs(lib)
        sm = os.path.join(lib, "SKILL.md")
        with open(sm, "w") as f:
            f.write("original")
        key1 = cache.cache_key_for_skill(sm)
        self._make_cache(lib, {"alpha-skill": {"key": key1}})
        # Change content but keep same mtime/size is hard; just verify different content = different key.
        with open(sm, "w") as f:
            f.write("changed content here")
        key2 = cache.cache_key_for_skill(sm)
        self.assertNotEqual(key1, key2)

    def test_removed_skill_invalidates(self):
        lib = os.path.join(self.td, "lib")
        os.makedirs(lib)
        sm = os.path.join(lib, "SKILL.md")
        with open(sm, "w") as f:
            f.write("hello")
        key = cache.cache_key_for_skill(sm)
        # Cache has two skills but only one exists now.
        self._make_cache(lib, {"alpha-skill": {"key": key}, "beta-skill": {"key": key}})
        entries = [("alpha-skill", sm)]
        self.assertFalse(cache.is_cache_valid(
            cache.load_cache(self.cache_file), lib, entries, cache.OVERRIDES_VERSION))

    def test_new_skill_invalidates(self):
        lib = os.path.join(self.td, "lib")
        os.makedirs(lib)
        sm = os.path.join(lib, "SKILL.md")
        with open(sm, "w") as f:
            f.write("hello")
        key = cache.cache_key_for_skill(sm)
        self._make_cache(lib, {})
        entries = [("alpha-skill", sm)]
        self.assertFalse(cache.is_cache_valid(
            cache.load_cache(self.cache_file), lib, entries, cache.OVERRIDES_VERSION))


if __name__ == "__main__":
    unittest.main()
