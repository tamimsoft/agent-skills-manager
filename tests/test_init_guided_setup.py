import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_skills import cli
from agent_skills.manifest import default_manifest, manifest_path, validate_manifest


class TestAgentManifestSettings(unittest.TestCase):
    def test_agent_enabled_defaults_on_for_legacy_manifest(self):
        manifest = default_manifest("project")
        manifest.pop("agents")
        self.assertTrue(cli.agent_is_enabled(manifest, "opencode"))

    def test_manifest_rejects_non_boolean_enabled(self):
        manifest = default_manifest("project")
        manifest["agents"]["junie"]["enabled"] = "false"
        self.assertIn("agents.junie.enabled must be a boolean", validate_manifest(manifest))

    def test_agent_availability_uses_configured_command(self):
        with patch.object(cli.shutil, "which", return_value="/tools/opencode"):
            self.assertEqual(
                cli._agent_availability({"agent_paths": {"opencode": "/tools/opencode"}}, "opencode"),
                "/tools/opencode",
            )

    def test_agent_picker_toggles_and_reports_availability(self):
        cfg = {"agent_paths": {}}
        with patch.object(
            cli, "_agent_availability",
            side_effect=["/bin/opencode", None, None, "/bin/opencode", None, None],
        ), \
                patch("builtins.input", side_effect=["2", ""]):
            with patch("builtins.print") as output:
                selected = cli.interactive_select_agents(cfg, ["opencode"])

        self.assertEqual(selected, ["opencode", "junie"])
        rendered = "\n".join(" ".join(str(arg) for arg in call.args) for call in output.call_args_list)
        self.assertIn("available", rendered)
        self.assertIn("not found", rendered)


class TestInteractiveSkillSearch(unittest.TestCase):
    def setUp(self):
        self.records = [
            {
                "dir_name": "common",
                "declared_name": "common",
                "description": "general workflow",
            },
            {
                "dir_name": "rare-skill",
                "declared_name": "rare",
                "description": "specialized hidden catalog skill",
            },
        ]

    def test_search_reaches_skills_outside_initial_recommendations(self):
        with patch.object(cli, "_curses_available", return_value=False), \
                patch("builtins.input", side_effect=["s specialized", "1", ""]):
            selected = cli.interactive_select(
                self.records, [], limit=1, initial_selected=set(),
            )

        self.assertEqual(selected, ["rare-skill"])

    def test_search_with_no_results_can_continue_browsing(self):
        with patch.object(cli, "_curses_available", return_value=False), \
                patch("builtins.input", side_effect=["s no-such-skill", "r", ""]):
            selected = cli.interactive_select(self.records, [], limit=1)

        self.assertEqual(selected, [])

    def test_cancel_is_distinct_from_confirming_an_empty_selection(self):
        with patch.object(cli, "_curses_available", return_value=False), \
                patch("builtins.input", return_value="q"):
            self.assertIsNone(cli.interactive_select(self.records, [], limit=1))
        with patch.object(cli, "_curses_available", return_value=False), \
                patch("builtins.input", return_value=""):
            self.assertEqual(cli.interactive_select(self.records, [], limit=1), [])


class TestGuidedInit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.cfg = {}
        self.args = SimpleNamespace(
            name=None, interactive=True, yes=True, dry_run=False,
        )

    def tearDown(self):
        self.temp.cleanup()

    def _run_init(self, root=None, args=None, **extra_patches):
        root = root or self.root
        args = args or self.args
        patches = [
            patch.object(cli, "find_project_root", return_value=root),
            patch.object(cli, "detect_technologies", return_value=[]),
            patch.object(cli, "_discover", return_value=(Path("/library"), [], [], [])),
            patch.object(cli, "interactive_select_agents", return_value=["opencode"]),
            patch.object(cli, "interactive_select", return_value=["chosen-skill"]),
            patch.object(
                cli, "generate_agents_md",
                side_effect=lambda *a, **kw: (False, "AGENTS updated", "managed block"),
            ),
        ]
        patches.extend(extra_patches.values())
        entered = []
        try:
            for item in patches:
                entered.append(item.start())
            with patch("sys.stdin.isatty", return_value=True):
                return cli.cmd_init(args, self.cfg)
        finally:
            for item in reversed(patches[:len(entered)]):
                item.stop()

    def test_guided_init_persists_agent_and_skill_choices_and_creates_dirs(self):
        self.assertEqual(self._run_init(), 0)
        manifest = json.loads(manifest_path(self.root).read_text())
        self.assertEqual(manifest["skills"]["selected"], ["chosen-skill"])
        self.assertTrue(manifest["agents"]["opencode"]["enabled"])
        self.assertFalse(manifest["agents"]["junie"]["enabled"])
        self.assertFalse(manifest["agents"]["kilo"]["enabled"])
        self.assertTrue((self.root / "docs" / "plans").is_dir())
        self.assertTrue((self.root / "docs" / "reviews").is_dir())

    def test_interactive_wizard_integrates_agent_choice_and_full_catalog_search(self):
        skill = {
            "dir_name": "rare-skill",
            "declared_name": "rare",
            "description": "specialized skill",
        }
        inputs = ["2", "", "s specialized", "1", ""]
        args = SimpleNamespace(name=None, interactive=True, yes=True, dry_run=False)
        with patch.object(cli, "find_project_root", return_value=self.root), \
                patch.object(cli, "detect_technologies", return_value=[]), \
                patch.object(cli, "_discover", return_value=(Path("/library"), [skill], [], [])), \
                patch.object(
                    cli, "generate_agents_md",
                    return_value=(False, "AGENTS updated", "managed block"),
                ), \
                patch.object(cli, "_curses_available", return_value=False), \
                patch("builtins.input", side_effect=inputs), \
                patch("sys.stdin.isatty", return_value=True):
            self.assertEqual(cli.cmd_init(args, self.cfg), 0)

        manifest = json.loads(manifest_path(self.root).read_text())
        self.assertEqual(manifest["skills"]["selected"], ["rare-skill"])
        self.assertTrue(manifest["agents"]["opencode"]["enabled"])
        self.assertFalse(manifest["agents"]["junie"]["enabled"])
        self.assertTrue(manifest["agents"]["kilo"]["enabled"])

    def test_guided_init_preserves_existing_project_metadata_and_unknown_agent(self):
        existing = default_manifest("old-name")
        existing["project"]["custom"] = "keep"
        existing["skills"]["selected"] = ["old-skill", "missing-skill"]
        existing["agents"]["custom-agent"] = {"enabled": False, "custom": True}
        manifest_path(self.root).parent.mkdir(parents=True)
        manifest_path(self.root).write_text(json.dumps(existing))

        self.assertEqual(self._run_init(), 0)
        updated = json.loads(manifest_path(self.root).read_text())
        self.assertEqual(updated["project"], {"name": "old-name", "custom": "keep"})
        self.assertEqual(updated["agents"]["custom-agent"], {"enabled": False, "custom": True})
        self.assertEqual(
            updated["skills"]["selected"],
            ["chosen-skill", "missing-skill", "old-skill"],
        )
        self.assertTrue(manifest_path(self.root).with_suffix(".json.bak").is_file())

    def test_cancelled_agent_selection_writes_nothing(self):
        with patch.object(cli, "find_project_root", return_value=self.root), \
                patch.object(cli, "detect_technologies", return_value=[]), \
                patch.object(cli, "_discover", return_value=(Path("/library"), [], [], [])), \
                patch.object(cli, "interactive_select_agents", return_value=None), \
                patch("sys.stdin.isatty", return_value=True):
            self.assertEqual(cli.cmd_init(self.args, self.cfg), 0)

        self.assertFalse(manifest_path(self.root).exists())
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse((self.root / "docs").exists())

    def test_interactive_yes_does_not_bypass_tty_requirement(self):
        with patch.object(cli, "find_project_root", return_value=self.root), \
                patch("sys.stdin.isatty", return_value=False):
            self.assertEqual(cli.cmd_init(self.args, self.cfg), 4)
        self.assertFalse(manifest_path(self.root).exists())

    def test_cancelled_skill_selection_does_not_save_agent_choices(self):
        with patch.object(cli, "find_project_root", return_value=self.root), \
                patch.object(cli, "detect_technologies", return_value=[]), \
                patch.object(cli, "_discover", return_value=(Path("/library"), [], [], [])), \
                patch.object(cli, "interactive_select_agents", return_value=["opencode"]), \
                patch.object(cli, "interactive_select", return_value=None), \
                patch("sys.stdin.isatty", return_value=True):
            self.assertEqual(cli.cmd_init(self.args, self.cfg), 0)

        self.assertFalse(manifest_path(self.root).exists())
        self.assertFalse((self.root / "docs").exists())

    def test_existing_invalid_manifest_is_not_replaced(self):
        manifest_path(self.root).parent.mkdir(parents=True)
        original = '{"schema_version": 1, "project": "invalid"}'
        manifest_path(self.root).write_text(original)
        args = SimpleNamespace(name=None, interactive=True, yes=True, dry_run=False)
        with patch.object(cli, "find_project_root", return_value=self.root), \
                patch("sys.stdin.isatty", return_value=True):
            self.assertEqual(cli.cmd_init(args, self.cfg), 1)

        self.assertEqual(manifest_path(self.root).read_text(), original)
        self.assertFalse((self.root / "docs").exists())

    def test_invalid_agents_preview_does_not_write_manifest(self):
        with patch.object(cli, "find_project_root", return_value=self.root), \
                patch.object(cli, "detect_technologies", return_value=[]), \
                patch.object(cli, "_discover", return_value=(Path("/library"), [], [], [])), \
                patch.object(cli, "interactive_select_agents", return_value=["opencode"]), \
                patch.object(cli, "interactive_select", return_value=["chosen-skill"]), \
                patch.object(cli, "generate_agents_md", return_value=(False, "bad template", None)), \
                patch("sys.stdin.isatty", return_value=True):
            self.assertEqual(cli.cmd_init(self.args, self.cfg), 1)

        self.assertFalse(manifest_path(self.root).exists())
        self.assertFalse((self.root / "docs").exists())

    def test_dry_run_does_not_write_manifest_or_workflow_directories(self):
        args = SimpleNamespace(name=None, interactive=True, yes=True, dry_run=True)
        self.assertEqual(self._run_init(args=args), 0)
        self.assertFalse(manifest_path(self.root).exists())
        self.assertFalse((self.root / "docs").exists())
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_plain_init_keeps_default_agents_and_creates_workflow_dirs(self):
        args = SimpleNamespace(name=None, interactive=False, yes=True, dry_run=False)
        self.assertEqual(self._run_init(args=args), 0)
        manifest = json.loads(manifest_path(self.root).read_text())
        self.assertEqual(
            {agent for agent, settings in manifest["agents"].items() if settings["enabled"]},
            {"junie", "opencode", "kilo"},
        )
        self.assertEqual(manifest["skills"]["selected"], [])
        self.assertTrue((self.root / "docs" / "plans").is_dir())
        self.assertTrue((self.root / "docs" / "reviews").is_dir())

    def test_init_allows_an_unconfigured_missing_skill_library(self):
        args = SimpleNamespace(name=None, interactive=False, yes=True, dry_run=False)
        with patch.object(cli, "find_project_root", return_value=self.root), \
                patch.object(cli, "detect_technologies", return_value=[]), \
                patch.object(cli, "resolve_library_root", return_value=self.root / "missing-library"), \
                patch.object(
                    cli, "_discover",
                    side_effect=cli.DiscoveryError("library root does not exist"),
                ), \
                patch.object(
                    cli, "generate_agents_md",
                    return_value=(False, "AGENTS updated", "managed block"),
                ):
            self.assertEqual(cli.cmd_init(args, self.cfg), 0)

        self.assertTrue(manifest_path(self.root).is_file())
        self.assertTrue((self.root / "docs" / "plans").is_dir())
        self.assertTrue((self.root / "docs" / "reviews").is_dir())

    def test_plain_init_does_not_replace_existing_manifest(self):
        existing = default_manifest("existing-name")
        existing["project"]["custom"] = "preserve"
        existing["skills"]["selected"] = ["existing-skill"]
        path = manifest_path(self.root)
        path.parent.mkdir(parents=True)
        original = json.dumps(existing, indent=2)
        path.write_text(original)
        args = SimpleNamespace(name=None, interactive=False, yes=False, dry_run=False)

        self.assertEqual(self._run_init(args=args), 0)
        self.assertEqual(path.read_text(), original)
        self.assertTrue((self.root / "docs" / "plans").is_dir())


if __name__ == "__main__":
    unittest.main()
