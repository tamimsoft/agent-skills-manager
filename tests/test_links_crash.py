"""Crash recovery and concurrency tests for build-then-swap (§15.3, R-04 / V21)."""

import os
import tempfile
import unittest
from pathlib import Path

from agent_skills.links import generate_project_skills_dir, MARKER_FILENAME, read_marker


def _make_record(dir_name, real_path, is_symlink=False):
    return {
        "dir_name": dir_name,
        "real_path": real_path,
        "is_symlink": is_symlink,
    }


class TestCrashRecovery(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.src = os.path.join(self.td, "src")
        self.lib = os.path.join(self.src, "lib")
        os.makedirs(self.lib)
        # Create a source skill with SKILL.md
        skill_dir = os.path.join(self.lib, "test-skill")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write("---\nname: test\ndescription: test\n---\n")
        self.gen = os.path.join(self.td, "gen")

    def test_normal_swap(self):
        rec = _make_record("test-skill", os.path.join(self.lib, "test-skill"))
        generate_project_skills_dir(self.gen, [rec], self.lib)
        self.assertTrue(os.path.isdir(self.gen))
        link = os.path.join(self.gen, "test-skill")
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.path.realpath(link), os.path.realpath(os.path.join(self.lib, "test-skill")))
        marker = read_marker(self.gen)
        self.assertIsNotNone(marker)
        self.assertEqual(marker["managed_entries"], ["test-skill"])

    def test_refresh_cleans_old_tmp_old(self):
        rec = _make_record("test-skill", os.path.join(self.lib, "test-skill"))
        generate_project_skills_dir(self.gen, [rec], self.lib)
        # Simulate leftover .tmp-* and .old-* from a crashed previous run.
        parent = os.path.dirname(self.gen)
        tmp_path = os.path.join(parent, ".gen-tmp-123")
        old_path = os.path.join(parent, ".gen-old-123")
        os.makedirs(tmp_path, exist_ok=True)
        os.makedirs(old_path, exist_ok=True)
        # Re-run should clean up leftovers.
        generate_project_skills_dir(self.gen, [rec], self.lib)
        self.assertFalse(os.path.exists(tmp_path))
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.islink(os.path.join(self.gen, "test-skill")))

    def test_deselected_skill_removed(self):
        # First run with one skill.
        rec1 = _make_record("skill-a", os.path.join(self.lib, "skill-a"))
        os.makedirs(os.path.join(self.lib, "skill-a"))
        with open(os.path.join(self.lib, "skill-a", "SKILL.md"), "w") as f:
            f.write("---\nname: a\ndescription: a\n---\n")
        generate_project_skills_dir(self.gen, [rec1], self.lib)
        self.assertTrue(os.path.islink(os.path.join(self.gen, "skill-a")))

        # Second run with no skills (deselect all).
        generate_project_skills_dir(self.gen, [], self.lib)
        self.assertFalse(os.path.exists(os.path.join(self.gen, "skill-a")))
        marker = read_marker(self.gen)
        self.assertEqual(marker["managed_entries"], [])


class TestConcurrencyLock(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.lib = os.path.join(self.td, "lib")
        os.makedirs(self.lib)
        skill_dir = os.path.join(self.lib, "test-skill")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write("---\nname: test\ndescription: test\n---\n")
        self.gen = os.path.join(self.td, "gen")

    def test_lock_serializes(self):
        from agent_skills.lock import AdvisoryLock
        lock_path = os.path.join(self.td, ".lock")
        acquired = []
        with AdvisoryLock(lock_path):
            acquired.append(1)
            # Try to acquire from same process (re-entrant not supported — should block/fail)
            import threading
            result = []

            def try_acquire():
                try:
                    with AdvisoryLock(lock_path):
                        result.append(2)
                except Exception as e:
                    result.append(str(e))

            t = threading.Thread(target=try_acquire)
            t.start()
            t.join(timeout=5)
            # The second thread should not acquire while the first holds the lock.
            self.assertNotIn(2, result)


if __name__ == "__main__":
    unittest.main()
