import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_skills.adapters import opencode
from agent_skills.adapters.opencode import (
    _apply_rules_to_config,
    _permission_rules,
)


class TestOpenCodeConfigRules(unittest.TestCase):
    def test_writes_documented_permission_shape_and_preserves_settings(self):
        existing = {
            "model": "provider/model",
            "permission": {"edit": "ask"},
        }
        config, sidecar, warnings = _apply_rules_to_config(
            existing, _permission_rules(["project-skill"]),
        )

        self.assertEqual(config["permission"]["skill"], {
            "*": "deny", "project-skill": "allow",
        })
        self.assertEqual(config["permission"]["edit"], "ask")
        self.assertEqual(config["model"], "provider/model")
        self.assertEqual(sidecar, {
            "schema_version": 1,
            "rules": {"*": "deny", "project-skill": "allow"},
        })
        self.assertEqual(warnings, [])

    def test_preserves_conflicting_user_wildcard(self):
        config, sidecar, warnings = _apply_rules_to_config(
            {"permission": {"skill": {"*": "allow"}}},
            _permission_rules(["project-skill"]),
        )

        self.assertEqual(config["permission"]["skill"]["*"], "allow")
        self.assertEqual(config["permission"]["skill"]["project-skill"], "allow")
        self.assertEqual(sidecar["rules"], {"project-skill": "allow"})
        self.assertTrue(any("preserving user OpenCode" in item for item in warnings))

    def test_removes_only_tagged_legacy_rules(self):
        existing = {
            "permissions": [
                {"action": "skill", "source": "agent-skills-manager"},
                {"action": "bash", "resource": "git *"},
            ],
            "policies": [
                {"action": "skill.use", "source": "agent-skills-manager"},
                {"action": "edit", "resource": "*.md"},
            ],
        }
        config, _, _ = _apply_rules_to_config(
            existing, _permission_rules([]),
        )

        self.assertEqual(config["permissions"], [
            {"action": "bash", "resource": "git *"},
        ])
        self.assertEqual(config["policies"], [
            {"action": "edit", "resource": "*.md"},
        ])

    def test_preserves_user_edits_to_previously_owned_rules(self):
        config, sidecar, warnings = _apply_rules_to_config(
            {"permission": {"skill": {"*": "deny", "project-skill": "ask"}}},
            _permission_rules(["project-skill"]),
            {"rules": {"*": "deny", "project-skill": "allow"}},
        )

        self.assertEqual(config["permission"]["skill"]["project-skill"], "ask")
        self.assertEqual(sidecar["rules"], {"*": "deny"})
        self.assertTrue(any("user-edited" in item for item in warnings))

    def test_reapplying_owned_rules_is_idempotent(self):
        rules = _permission_rules(["project-skill"])
        first_config, first_sidecar, _ = _apply_rules_to_config({}, rules)
        second_config, second_sidecar, warnings = _apply_rules_to_config(
            first_config, rules, first_sidecar,
        )
        self.assertEqual(second_config, first_config)
        self.assertEqual(second_sidecar, first_sidecar)
        self.assertEqual(warnings, [])


class TestOpenCodeDryRun(unittest.TestCase):
    def test_apply_dry_run_does_not_modify_project_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".agents").mkdir()
            (root / ".agents" / "skills.json").write_text(json.dumps({
                "schema_version": 1,
                "project": {"name": "test"},
                "skills": {"selected": []},
                "agents": {},
            }))
            config_path = root / "opencode.json"
            original_config = {"model": "provider/model"}
            config_path.write_text(json.dumps(original_config))

            with patch.object(opencode, "find_project_root", return_value=root), \
                    patch.object(opencode, "_agent_ids_for_selected", return_value=([], [], {})), \
                    patch.object(opencode, "detect_technologies", return_value=[]):
                rc, message = opencode.apply(
                    {"skill_context_budget_tokens": 0, "max_skills_in_context": 0},
                    dry_run=True,
                    yes=True,
                )

            self.assertEqual(rc, 0)
            self.assertIn("would write", message)
            self.assertEqual(json.loads(config_path.read_text()), original_config)
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / ".agents" / "opencode-owned-rules.json").exists())


if __name__ == "__main__":
    unittest.main()
