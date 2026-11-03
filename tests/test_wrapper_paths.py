"""Wrapper relative-path tests (§15.4, R-08 / V19).

Verifies the wrapper layout preserves nested folders, executable scripts,
and paths with spaces for frontmatter-less skills.
"""

import hashlib
import os
import tempfile
import unittest

from agent_skills.adapter_common import build_wrapper, build_skill_entry


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class TestWrapperRelativePaths(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.src = os.path.join(self.td, "src-skill")
        os.makedirs(self.src)
        # No frontmatter skill with nested folder, script, and space in name.
        with open(os.path.join(self.src, "SKILL.md"), "w") as f:
            f.write("# No Frontmatter Skill\n\nbody content\n")
        # Nested folder with a file.
        nested_dir = os.path.join(self.src, "nested folder")
        os.makedirs(nested_dir)
        with open(os.path.join(nested_dir, "config.yaml"), "w") as f:
            f.write("key: value\n")
        # Executable script.
        scripts_dir = os.path.join(self.src, "scripts")
        os.makedirs(scripts_dir)
        with open(os.path.join(scripts_dir, "run-check.sh"), "w") as f:
            f.write("#!/usr/bin/env bash\necho hello\n")
        os.chmod(os.path.join(scripts_dir, "run-check.sh"), 0o755)
        # Space-containing filename at top level.
        with open(os.path.join(self.src, "read me.txt"), "w") as f:
            f.write("readme\n")
        self.dest = os.path.join(self.td, "dest")
        os.makedirs(self.dest)

    def test_wrapper_preserves_nested_folder(self):
        rec = {"dir_name": "src-skill", "real_path": self.src}
        linked = build_skill_entry(self.src, self.dest, rec)
        # Skill subdirectory created.
        skill_dest = os.path.join(self.dest, "src-skill")
        self.assertTrue(os.path.isdir(skill_dest))
        # SKILL.md regenerated with frontmatter inside skill dir.
        self.assertTrue(os.path.isfile(os.path.join(skill_dest, "SKILL.md")))
        with open(os.path.join(skill_dest, "SKILL.md"), "r") as f:
            md = f.read()
        self.assertIn("name: src-skill", md)
        self.assertIn("description: ", md)
        # Nested folder is a real directory with symlinked contents.
        nested_dest = os.path.join(skill_dest, "nested folder")
        self.assertTrue(os.path.isdir(nested_dest))
        self.assertFalse(os.path.islink(nested_dest))
        config_dest = os.path.join(nested_dest, "config.yaml")
        self.assertTrue(os.path.islink(config_dest))
        self.assertTrue(os.path.exists(config_dest))
        # Script symlinked and executable bit preserved.
        script_dest = os.path.join(skill_dest, "scripts", "run-check.sh")
        self.assertTrue(os.path.islink(script_dest))
        self.assertTrue(os.access(script_dest, os.X_OK))
        # Space-containing file symlinked inside skill dir.
        readme_dest = os.path.join(skill_dest, "read me.txt")
        self.assertTrue(os.path.islink(readme_dest))
        self.assertTrue(os.path.exists(readme_dest))
        # Linked entries reported relative to skill dir.
        self.assertTrue(any("nested folder/config.yaml" in l for l in linked))
        self.assertTrue(any("scripts/run-check.sh" in l for l in linked))
        self.assertTrue(any("read me.txt" in l for l in linked))

    def test_originals_unchanged_by_checksum(self):
        rec = {"dir_name": "src-skill", "real_path": self.src}
        before = {}
        for root, _, files in os.walk(self.src):
            for fn in files:
                fp = os.path.join(root, fn)
                before[fp] = _sha256_file(fp)
        build_skill_entry(self.src, self.dest, rec)
        after = {}
        for root, _, files in os.walk(self.src):
            for fn in files:
                fp = os.path.join(root, fn)
                after[fp] = _sha256_file(fp)
        self.assertEqual(before, after)

    def test_build_skill_entry_uses_wrapper_for_no_frontmatter(self):
        rec = {"dir_name": "src-skill", "real_path": self.src}
        linked = build_skill_entry(self.src, self.dest, rec)
        self.assertTrue(os.path.isdir(os.path.join(self.dest, "src-skill")))
        self.assertTrue(any("nested folder" in l for l in linked))

    def test_build_skill_entry_direct_symlink_for_valid_frontmatter(self):
        # Create a separate skill with valid frontmatter.
        vf_src = os.path.join(self.td, "vf-skill")
        os.makedirs(vf_src)
        with open(os.path.join(vf_src, "SKILL.md"), "w") as f:
            f.write("---\nname: vf\ndescription: valid frontmatter\n---\n")
        rec = {"dir_name": "vf-skill", "real_path": vf_src}
        vf_dest = os.path.join(self.td, "vf-dest")
        os.makedirs(vf_dest)
        linked = build_skill_entry(vf_src, vf_dest, rec)
        self.assertTrue(os.path.islink(os.path.join(vf_dest, "vf-skill")))
        self.assertEqual(linked, [])


if __name__ == "__main__":
    unittest.main()
