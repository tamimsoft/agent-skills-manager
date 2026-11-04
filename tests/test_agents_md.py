"""Tests for AGENTS.md hard enforcement feature.

Covers:
- generate_agents_md() default (no overwrite), force=True overwrite, write=False dry-run
- cmd_sync() regenerates AGENTS.md
- cmd_validate() exits 3 when AGENTS.md missing, passes when present/current
- generate_project_skills_dir() writes AGENTS.md into generated dir
- L1: cmd_validate() reports missing skills even with empty library
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_skills import cli
from agent_skills.adapter_common import build_skill_entry, build_skills_dir_atomic
from agent_skills.agents_md import (
    BEGIN_MARKER,
    END_MARKER,
    generate_agents_md,
)
from agent_skills.links import read_marker


def _make_record(dir_name, real_path):
    return {
        "dir_name": dir_name,
        "real_path": real_path,
    }


class TestGenerateAgentsMd(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.home = Path(self.td) / "home"
        os.environ["AGENT_SKILLS_HOME"] = str(self.home)
        os.environ["AGENT_SKILLS_CONFIG"] = str(self.home / "config.json")
        self.root = Path(self.td) / "myproject"
        self.root.mkdir()
        (self.root / ".agents").mkdir()

    def tearDown(self):
        os.environ.pop("AGENT_SKILLS_HOME", None)
        os.environ.pop("AGENT_SKILLS_CONFIG", None)

    def test_generate_when_missing(self):
        wrote, msg, content = generate_agents_md(self.root, [], {})
        self.assertTrue(wrote)
        self.assertTrue((self.root / "AGENTS.md").is_file())
        self.assertIn("# Agent Instructions", content)
        self.assertIn(BEGIN_MARKER, content)
        self.assertIn(END_MARKER, content)

    def test_existing_content_is_backed_up_and_preserved(self):
        original = "# User rules\n\nKeep this text.\n"
        path = self.root / "AGENTS.md"
        path.write_text(original)
        wrote, msg, content = generate_agents_md(self.root, [], {})
        self.assertTrue(wrote)
        actual = path.read_text()
        self.assertTrue(actual.startswith(original))
        self.assertIn(BEGIN_MARKER, actual)
        backups = list((self.root / ".agents" / "backups").glob("AGENTS.md.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)

    def test_refresh_replaces_only_managed_block(self):
        path = self.root / "AGENTS.md"
        original = "User top\n%s\nold managed text\n%s\nUser bottom\n" % (
            BEGIN_MARKER, END_MARKER,
        )
        path.write_text(original)
        wrote, msg, content = generate_agents_md(
            self.root, [{"name": "flutter", "evidence": [{"file": "pubspec.yaml"}]}], {},
        )
        self.assertTrue(wrote)
        actual = path.read_text()
        self.assertTrue(actual.startswith("User top\n"))
        self.assertTrue(actual.endswith("\nUser bottom\n"))
        self.assertIn("flutter", actual)
        self.assertNotIn("old managed text", actual)
        self.assertFalse((self.root / ".agents" / "backups").exists())

    def test_malformed_markers_are_not_modified(self):
        path = self.root / "AGENTS.md"
        original = "User rules\n%s\n" % BEGIN_MARKER
        path.write_text(original)
        wrote, msg, content = generate_agents_md(self.root, [], {})
        self.assertFalse(wrote)
        self.assertIsNone(content)
        self.assertIn("malformed", msg)
        self.assertEqual(path.read_text(), original)

    def test_write_false_does_not_write(self):
        original = "# User rules\n"
        (self.root / "AGENTS.md").write_text(original)
        wrote, msg, content = generate_agents_md(self.root, [], {}, force=True, write=False)
        self.assertFalse(wrote)
        self.assertEqual((self.root / "AGENTS.md").read_text(), original)
        self.assertIn(BEGIN_MARKER, content)
        self.assertFalse((self.root / ".agents" / "backups").exists())

    def test_with_techs(self):
        techs = [{"name": "flutter", "evidence": [{"file": "pubspec.yaml"}]}]
        wrote, msg, content = generate_agents_md(self.root, techs, {})
        self.assertTrue(wrote)
        self.assertIn("flutter", content)
        self.assertIn("pubspec.yaml", content)


class TestGenerateProjectSkillsDirWritesAgentsMd(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.lib = Path(self.td) / "lib"
        self.lib.mkdir()
        skill_dir = self.lib / "test-skill"
        skill_dir.mkdir()
        with open(skill_dir / "SKILL.md", "w") as f:
            f.write("---\nname: test\ndescription: test\n---\n")
        self.gen = Path(self.td) / "gen"

    def test_agents_md_written_into_generated_dir(self):
        rec = _make_record("test-skill", str(self.lib / "test-skill"))
        content = "# Agent Instructions\ntest\n"
        build_skills_dir_atomic(
            parent=self.gen.parent,
            dest_dir=self.gen,
            records=[rec],
            agent_name="manager",
            key="test-project",
            build_entry_fn=build_skill_entry,
            agents_md_content=content,
        )
        agents_md = self.gen / "AGENTS.md"
        self.assertTrue(agents_md.is_file())
        self.assertEqual(agents_md.read_text(), content + "\n")
        marker = read_marker(self.gen)
        self.assertIn("AGENTS.md", marker["managed_entries"])

    def test_no_agents_md_when_content_none(self):
        rec = _make_record("test-skill", str(self.lib / "test-skill"))
        build_skills_dir_atomic(
            parent=self.gen.parent,
            dest_dir=self.gen,
            records=[rec],
            agent_name="manager",
            key="test-project",
            build_entry_fn=build_skill_entry,
        )
        agents_md = self.gen / "AGENTS.md"
        self.assertFalse(agents_md.exists())


class TestValidateAgentsMd(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        os.environ["AGENT_SKILLS_HOME"] = self.td
        os.environ["AGENT_SKILLS_CONFIG"] = os.path.join(self.td, "config.json")
        self.old_cwd = os.getcwd()
        self.root = Path(self.td) / "myproject"
        self.root.mkdir()
        (self.root / ".agents").mkdir()
        # Create library root so discovery doesn't fail
        lib_root = Path(self.td) / ".agents" / "skills"
        lib_root.mkdir(parents=True)
        self.manifest = self.root / ".agents" / "skills.json"
        self.manifest.write_text(json.dumps({
            "schema_version": 1,
            "project": {"name": "myproject"},
            "skills": {"selected": []},
            "agents": {
                "junie": {"enabled": True},
                "opencode": {"enabled": True},
                "kilo": {"enabled": True},
            },
        }))

    def tearDown(self):
        os.chdir(self.old_cwd)
        os.environ.pop("AGENT_SKILLS_HOME", None)
        os.environ.pop("AGENT_SKILLS_CONFIG", None)

    def _run_validate(self):
        from agent_skills.cli import cmd_validate
        import sys
        from io import StringIO
        os.chdir(self.root)
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            rc = cmd_validate(None, {})
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout
        return rc, output

    def test_validate_passes_with_agents_md(self):
        generate_agents_md(self.root, [], {})
        rc, output = self._run_validate()
        self.assertEqual(rc, 0)

    def test_validate_fails_without_agents_md(self):
        rc, output = self._run_validate()
        self.assertEqual(rc, 3)
        self.assertIn("AGENTS.md missing", output)

    def test_validate_reports_missing_skill_even_with_empty_library(self):
        # L1: rec_map is empty (no library), but manifest selects a skill
        self.manifest.write_text(json.dumps({
            "schema_version": 1,
            "project": {"name": "myproject"},
            "skills": {"selected": ["nonexistent-skill"]},
            "agents": {},
        }))
        rc, output = self._run_validate()
        self.assertEqual(rc, 3)
        self.assertIn("manifest references missing skill: nonexistent-skill", output)


class TestSyncDryRun(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.home = Path(self.td) / "home"
        self.root = Path(self.td) / "project"
        (self.root / ".agents").mkdir(parents=True)
        self.library = Path(self.td) / "library"
        self.library.mkdir()
        self.generated_root = Path(self.td) / "generated"
        self.manifest = self.root / ".agents" / "skills.json"
        self.manifest.write_text(json.dumps({
            "schema_version": 1,
            "project": {"name": "project"},
            "skills": {"selected": []},
            "agents": {},
        }))
        self.old_cwd = os.getcwd()
        os.environ["AGENT_SKILLS_HOME"] = str(self.home)
        os.environ["AGENT_SKILLS_CONFIG"] = str(self.home / "config.json")

    def tearDown(self):
        os.chdir(self.old_cwd)
        os.environ.pop("AGENT_SKILLS_HOME", None)
        os.environ.pop("AGENT_SKILLS_CONFIG", None)

    def test_dry_run_does_not_write_agents_or_generated_files(self):
        os.chdir(self.root)
        cfg = {
            "library_root": str(self.library),
            "generated_root": str(self.generated_root),
            "skill_context_budget_tokens": 32768,
            "max_skills_in_context": 50,
        }
        with patch.object(cli, "_discover", return_value=(self.library, [], [], [])):
            rc = cli.cmd_sync(SimpleNamespace(dry_run=True), cfg)

        self.assertEqual(rc, 0)
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse(self.generated_root.exists())
        self.assertFalse((self.home / ".config" / "agent-skills" / "templates").exists())

    def test_sync_builds_atomic_directory_and_owned_rules_sidecar(self):
        os.chdir(self.root)
        skill = self.library / "project-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: project-skill\ndescription: project skill\n---\n"
        )
        self.manifest.write_text(json.dumps({
            "schema_version": 1,
            "project": {"name": "project"},
            "skills": {"selected": ["project-skill"]},
            "agents": {},
        }))
        record = {
            "dir_name": "project-skill",
            "real_path": str(skill),
            "declared_name": "project-skill",
            "description": "project skill",
        }
        cfg = {
            "library_root": str(self.library),
            "generated_root": str(self.generated_root),
            "skill_context_budget_tokens": 32768,
            "max_skills_in_context": 50,
        }
        with patch.object(cli, "_discover", return_value=(self.library, [record], [], [])):
            rc = cli.cmd_sync(SimpleNamespace(dry_run=False), cfg)

        self.assertEqual(rc, 0)
        generated = next(path for path in self.generated_root.iterdir() if path.is_dir())
        self.assertTrue((generated / "project-skill").is_symlink())
        marker = read_marker(generated)
        self.assertEqual(marker["managed_entries"], ["project-skill", "AGENTS.md"])
        owned = json.loads((generated / "opencode-owned-rules.json").read_text())
        self.assertEqual(owned["managed_entries"], marker["managed_entries"])
        self.assertTrue((self.root / "AGENTS.md").is_file())

    def test_init_dry_run_does_not_create_manifest_or_agents_file(self):
        os.chdir(self.root)
        self.manifest.unlink()
        args = SimpleNamespace(
            name=None, interactive=False, yes=False, dry_run=True,
        )
        cfg = {"library_root": str(self.library)}
        with patch.object(cli, "find_project_root", return_value=self.root), \
                patch.object(cli, "_discover", return_value=(self.library, [], [], [])):
            rc = cli.cmd_init(args, cfg)

        self.assertEqual(rc, 0)
        self.assertFalse(self.manifest.exists())
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse((self.home / ".config" / "agent-skills" / "templates").exists())


if __name__ == "__main__":
    unittest.main()
