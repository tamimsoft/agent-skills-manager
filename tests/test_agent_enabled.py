import json
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_skills.adapters import junie, kilo, opencode
from agent_skills.manifest import default_manifest, manifest_path


class TestDisabledManagedAgents(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        manifest = default_manifest("project")
        manifest["agents"]["junie"]["enabled"] = False
        manifest["agents"]["kilo"]["enabled"] = False
        manifest["agents"]["opencode"]["enabled"] = False
        path = manifest_path(self.root)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(manifest))

    def tearDown(self):
        self.temp.cleanup()

    def test_junie_managed_launch_is_blocked(self):
        args = SimpleNamespace(prepare=False, dry_run=False, args=[])
        with patch.object(junie, "find_project_root", return_value=self.root):
            self.assertEqual(junie.launch_junie(args, {}), 4)

    def test_kilo_managed_apply_is_blocked(self):
        args = SimpleNamespace(dry_run=False, yes=True, run_kilo=False, args=[])
        with patch.object(kilo, "find_project_root", return_value=self.root):
            self.assertEqual(kilo.launch_kilo(args, {}), 4)

    def test_opencode_managed_apply_is_blocked(self):
        with patch.object(opencode, "find_project_root", return_value=self.root):
            rc, message = opencode.apply({}, yes=True)

        self.assertEqual(rc, 4)
        self.assertIn("OpenCode is disabled", message)

    def test_opencode_reports_missing_executable_without_traceback(self):
        error_output = StringIO()
        with patch.object(opencode, "apply", return_value=(0, "applied")), \
                patch.object(opencode, "validate", return_value=(0, "valid")), \
                patch.object(opencode, "_opencode_exe", return_value="missing-opencode"), \
                patch.object(opencode.os, "execvp", side_effect=FileNotFoundError("missing")), \
                redirect_stderr(error_output):
            rc = opencode.run({})

        self.assertEqual(rc, 127)
        self.assertIn("unable to launch OpenCode", error_output.getvalue())
        self.assertIn("agent_paths.opencode", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()
