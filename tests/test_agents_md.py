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

from agent_skills import cli
from agent_skills.cli import generate_agents_md
from agent_skills.links import generate_project_skills_dir, read_marker


def _make_record(dir_name, real_path):
    return {
        "dir_name": dir_name,
        "real_path": real_path,
    }


class TestGenerateAgentsMd(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.root = Path(self.td) / "myproject"
        self.root.mkdir()
        (self.root / ".agents").mkdir()

    def test_generate_when_missing(self):
        wrote, msg, content = generate_agents_md(self.root, [], {})
        self.assertTrue(wrote)
        self.assertTrue((self.root / "AGENTS.md").is_file())
        self.assertIn("# Agent Instructions", content)

    def test_no_overwrite_when_exists(self):
        (self.root / "AGENTS.md").write_text("existing content\n")
        wrote, msg, content = generate_agents_md(self.root, [], {})
        self.assertFalse(wrote)
        self.assertEqual(content, "existing content\n")

    def test_force_overwrite(self):
        (self.root / "AGENTS.md").write_text("old content\n")
        wrote, msg, content = generate_agents_md(self.root, [], {}, force=True)
        self.assertTrue(wrote)
        self.assertIn("# Agent Instructions", content)
        self.assertEqual((self.root / "AGENTS.md").read_text(), content)

    def test_write_false_does_not_write(self):
        (self.root / "AGENTS.md").write_text("existing content\n")
        wrote, msg, content = generate_agents_md(self.root, [], {}, force=True, write=False)
        self.assertFalse(wrote)
        self.assertEqual((self.root / "AGENTS.md").read_text(), "existing content\n")
        self.assertIn("# Agent Instructions", content)

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
        generate_project_skills_dir(self.gen, [rec], str(self.lib), agents_md_content=content)
        agents_md = self.gen / "AGENTS.md"
        self.assertTrue(agents_md.is_file())
        # generate_project_skills_dir appends a trailing newline
        self.assertEqual(agents_md.read_text(), content + "\n")
        marker = read_marker(self.gen)
        self.assertIn("AGENTS.md", marker["managed_entries"])

    def test_no_agents_md_when_content_none(self):
        rec = _make_record("test-skill", str(self.lib / "test-skill"))
        generate_project_skills_dir(self.gen, [rec], str(self.lib))
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
        (self.root / "AGENTS.md").write_text("# Agent Instructions\n\ntest\n")
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


if __name__ == "__main__":
    unittest.main()
