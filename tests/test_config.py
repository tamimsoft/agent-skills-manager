import os
import tempfile
import unittest

from agent_skills import config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        os.environ["AGENT_SKILLS_HOME"] = self.td
        os.environ["AGENT_SKILLS_CONFIG"] = os.path.join(self.td, "config.json")

    def tearDown(self):
        os.environ.pop("AGENT_SKILLS_HOME", None)
        os.environ.pop("AGENT_SKILLS_CONFIG", None)

    def test_default_config_created_on_load(self):
        cfg, errs = config.load_config()
        self.assertEqual(errs, [])
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["schema_version"], config.SCHEMA_VERSION)

    def test_save_and_reload(self):
        cfg, _ = config.load_config()
        cfg["skill_overrides"] = {"x": {"name": "x", "description": "d"}}
        config.save_config(cfg)
        cfg2, errs = config.load_config()
        self.assertEqual(errs, [])
        self.assertEqual(cfg2["skill_overrides"]["x"]["description"], "d")

    def test_validation_error(self):
        cfg, _ = config.load_config()
        cfg["allowed_roots"] = "not-a-list"
        with self.assertRaises(ValueError):
            config.save_config(cfg)

    def test_backup_created(self):
        cfg, _ = config.load_config()
        config.save_config(cfg)
        cfg2, _ = config.load_config()
        config.save_config(cfg2)
        backup = config.config_path().with_suffix(config.config_path().suffix + ".bak")
        self.assertTrue(backup.exists())

    def test_env_override_home(self):
        self.assertEqual(str(config.home_dir()), os.path.realpath(self.td))


if __name__ == "__main__":
    unittest.main()