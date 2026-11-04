import os
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_skills.adapter_common import build_skill_copy
from agent_skills.adapters import kilo
from agent_skills.adapters.kilo import _apply_kilo_rules


class TestKiloConfigRules(unittest.TestCase):
    def test_writes_nested_skill_rules_and_preserves_other_permissions(self):
        existing = {
            "permission": {
                "bash": {"git *": "allow"},
                "skill": {"internal-*": "deny"},
            },
            "other": True,
        }
        config, sidecar, warnings = _apply_kilo_rules(
            existing, {"*": "deny", "project-skill": "allow"},
        )

        self.assertEqual(config["permission"]["skill"], {
            "*": "deny",
            "internal-*": "deny",
            "project-skill": "allow",
        })
        self.assertEqual(config["permission"]["bash"], {"git *": "allow"})
        self.assertTrue(config["other"])
        self.assertNotIn("_agent_skills_managed", config["permission"])
        self.assertEqual(sidecar, {
            "schema_version": 1,
            "rules": {"*": "deny", "project-skill": "allow"},
        })
        self.assertEqual(warnings, [])

    def test_preserves_user_wildcard_and_reports_conflict(self):
        config, sidecar, warnings = _apply_kilo_rules(
            {"permission": {"skill": {"*": "allow"}}},
            {"*": "deny", "project-skill": "allow"},
        )

        self.assertEqual(config["permission"]["skill"]["*"], "allow")
        self.assertEqual(config["permission"]["skill"]["project-skill"], "allow")
        self.assertEqual(sidecar["rules"], {"project-skill": "allow"})
        self.assertTrue(any("preserving user Kilo" in warning for warning in warnings))

    def test_migrates_only_tracked_legacy_flat_rules(self):
        existing = {
            "permission": {
                "*": "deny",
                "old-skill": "allow",
                "user-rule": "ask",
                "_agent_skills_managed": ["*", "old-skill"],
                "bash": {"git *": "allow"},
            },
        }
        config, sidecar, warnings = _apply_kilo_rules(
            existing, {"*": "deny", "new-skill": "allow"},
        )

        self.assertNotIn("*", config["permission"])
        self.assertNotIn("old-skill", config["permission"])
        self.assertEqual(config["permission"]["user-rule"], "ask")
        self.assertEqual(config["permission"]["bash"], {"git *": "allow"})
        self.assertEqual(config["permission"]["skill"], {
            "*": "deny", "new-skill": "allow",
        })
        self.assertEqual(warnings, [])
        self.assertEqual(sidecar["rules"], {"*": "deny", "new-skill": "allow"})

    def test_preserves_user_edits_to_previously_owned_rules(self):
        config, sidecar, warnings = _apply_kilo_rules(
            {"permission": {"skill": {"*": "deny", "project-skill": "ask"}}},
            {"*": "deny", "project-skill": "allow"},
            {"rules": {"*": "deny", "project-skill": "allow"}},
        )

        self.assertEqual(config["permission"]["skill"]["project-skill"], "ask")
        self.assertEqual(sidecar["rules"], {"*": "deny"})
        self.assertTrue(any("user-edited" in warning for warning in warnings))

    def test_reapplying_owned_rules_is_idempotent(self):
        rules = {"*": "deny", "project-skill": "allow"}
        first_config, first_sidecar, _ = _apply_kilo_rules({}, rules)
        second_config, second_sidecar, warnings = _apply_kilo_rules(
            first_config, rules, first_sidecar,
        )
        self.assertEqual(second_config, first_config)
        self.assertEqual(second_sidecar, first_sidecar)
        self.assertEqual(warnings, [])


class TestKiloSkillCopy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.skill = self.root / "library" / "skill"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: skill\ndescription: test\n---\n")
        (self.skill / "guide.md").write_text("guide content")
        self.destination = self.root / "project-skills"
        self.destination.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_copies_selected_skill_bundle_into_real_directory(self):
        build_skill_copy(self.skill, self.destination, {"dir_name": "skill"})
        copied = self.destination / "skill"
        self.assertTrue(copied.is_dir())
        self.assertFalse(copied.is_symlink())
        self.assertEqual((copied / "SKILL.md").read_text(), (self.skill / "SKILL.md").read_text())
        self.assertEqual((copied / "guide.md").read_text(), "guide content")

    def test_rejects_bundle_symlink_that_escapes_skill_root(self):
        outside = self.root / "outside.txt"
        outside.write_text("outside")
        os.symlink(outside, self.skill / "outside.txt")
        with self.assertRaisesRegex(RuntimeError, "escapes skill root"):
            build_skill_copy(self.skill, self.destination, {"dir_name": "skill"})


class TestKiloDryRun(unittest.TestCase):
    def test_apply_dry_run_does_not_write_project_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".agents").mkdir()
            (root / ".agents" / "skills.json").write_text(json.dumps({
                "schema_version": 1,
                "project": {"name": "test"},
                "skills": {"selected": []},
                "agents": {"kilo": {"enabled": True}},
            }))
            args = SimpleNamespace(args=[], dry_run=True, yes=True, run_kilo=False)
            cfg = {
                "library_root": str(root / "library"),
                "skill_context_budget_tokens": 0,
                "max_skills_in_context": 0,
            }
            with patch.object(kilo, "find_project_root", return_value=root), \
                    patch.object(kilo, "discover_skills", return_value=([], [], [])), \
                    patch.object(kilo, "detect_technologies", return_value=[]):
                rc = kilo.launch_kilo(args, cfg)

            self.assertEqual(rc, 0)
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / ".kilo").exists())
            self.assertFalse((root / ".agents" / "kilo-owned-rules.json").exists())


if __name__ == "__main__":
    unittest.main()
