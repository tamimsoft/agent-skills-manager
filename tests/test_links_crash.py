"""Crash recovery and concurrency tests for build-then-swap (§15.3, R-04 / V21)."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from agent_skills.adapter_common import build_skill_entry, build_skills_dir_atomic
from agent_skills.links import read_marker


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

    def _build(self, records):
        return build_skills_dir_atomic(
            parent=Path(self.td),
            dest_dir=Path(self.gen),
            records=records,
            agent_name="manager",
            key="test-project",
            build_entry_fn=build_skill_entry,
            tmp_prefix=".gen-tmp-",
        )

    def test_normal_swap(self):
        rec = _make_record("test-skill", os.path.join(self.lib, "test-skill"))
        self._build([rec])
        self.assertTrue(os.path.isdir(self.gen))
        link = os.path.join(self.gen, "test-skill")
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.path.realpath(link), os.path.realpath(os.path.join(self.lib, "test-skill")))
        marker = read_marker(self.gen)
        self.assertIsNotNone(marker)
        self.assertEqual(marker["managed_entries"], ["test-skill"])
        self.assertEqual(marker["agent"], "manager")

    def test_cleanup_targets_only_owned_temporary_prefix(self):
        rec = _make_record("test-skill", os.path.join(self.lib, "test-skill"))
        tmp_path = Path(self.td) / ".gen-tmp-abandoned"
        unmarked_tmp = Path(self.td) / ".gen-tmp-user-data"
        unrelated_path = Path(self.td) / ".gen-other"
        old_path = Path(self.td) / ".gen-tmp-old-unmarked"
        tmp_path.mkdir()
        unmarked_tmp.mkdir()
        (tmp_path / ".agent-skills-build.json").write_text(json.dumps({
            "project_key": "test-project",
            "agent": "manager",
        }))
        unrelated_path.mkdir()
        old_path.mkdir()
        self._build([rec])
        self.assertFalse(tmp_path.exists())
        self.assertTrue(unmarked_tmp.exists())
        self.assertTrue(unrelated_path.exists())
        self.assertTrue(old_path.exists())
        self.assertTrue(os.path.islink(os.path.join(self.gen, "test-skill")))

    def test_restores_marked_old_directory_after_interrupted_swap(self):
        rec = _make_record("test-skill", os.path.join(self.lib, "test-skill"))
        self._build([rec])
        old_path = Path(self.td) / ".gen-tmp-old-crashed"
        os.replace(self.gen, old_path)
        self.assertFalse(Path(self.gen).exists())
        self._build([rec])
        self.assertTrue(os.path.islink(os.path.join(self.gen, "test-skill")))
        self.assertFalse(old_path.exists())

    def test_restores_legacy_old_directory_name(self):
        rec = _make_record("test-skill", os.path.join(self.lib, "test-skill"))
        self._build([rec])
        old_path = Path(self.td) / ".gen-tmp.old-123"
        os.replace(self.gen, old_path)
        self._build([rec])
        self.assertTrue(os.path.islink(os.path.join(self.gen, "test-skill")))
        self.assertFalse(old_path.exists())

    def test_unmarked_destination_is_preserved(self):
        os.makedirs(self.gen)
        user_file = Path(self.gen) / "user-file"
        user_file.write_text("keep")
        rec = _make_record("test-skill", os.path.join(self.lib, "test-skill"))
        with self.assertRaisesRegex(RuntimeError, "unmarked generated directory"):
            self._build([rec])
        self.assertEqual(user_file.read_text(), "keep")

    def test_deselected_skill_removed(self):
        # First run with one skill.
        rec1 = _make_record("skill-a", os.path.join(self.lib, "skill-a"))
        os.makedirs(os.path.join(self.lib, "skill-a"))
        with open(os.path.join(self.lib, "skill-a", "SKILL.md"), "w") as f:
            f.write("---\nname: a\ndescription: a\n---\n")
        self._build([rec1])
        self.assertTrue(os.path.islink(os.path.join(self.gen, "skill-a")))

        # Second run with no skills (deselect all).
        self._build([])
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
