import unittest

from agent_skills.cli import _build_parser


class TestCliFlags(unittest.TestCase):
    def setUp(self):
        self.parser = _build_parser()

    def test_action_flags_belong_to_subcommands(self):
        args = self.parser.parse_args(["sync", "--dry-run"])
        self.assertTrue(args.dry_run)

        with self.assertRaises(SystemExit):
            self.parser.parse_args(["--yes", "sync"])
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["sync", "--yes"])

    def test_nested_kilo_run_accepts_yes(self):
        args = self.parser.parse_args(["kilo", "run", "--yes"])
        self.assertEqual(args.kilo_sub, "run")
        self.assertTrue(args.yes)
        self.assertFalse(args.dry_run)

    def test_nested_adapter_commands_accept_dry_run(self):
        kilo = self.parser.parse_args(["kilo", "apply", "--dry-run"])
        self.assertTrue(kilo.dry_run)

        opencode = self.parser.parse_args(["opencode", "apply", "--dry-run"])
        self.assertTrue(opencode.dry_run)

    def test_options_after_positional_skill_ids_are_parsed(self):
        args = self.parser.parse_args(["add", "flutter-skill", "--yes"])
        self.assertEqual(args.skills, ["flutter-skill"])
        self.assertTrue(args.yes)


if __name__ == "__main__":
    unittest.main()
