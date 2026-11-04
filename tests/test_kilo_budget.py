import unittest

from agent_skills.adapters.kilo import _kilo_permission_rules_for_records


class TestKiloPermissionBudget(unittest.TestCase):
    def test_only_generated_skills_are_allowed(self):
        filtered_records = [
            {"dir_name": "allowed-skill", "declared_name": "allowed"},
        ]

        rules = _kilo_permission_rules_for_records(filtered_records)

        self.assertEqual(rules, {
            "*": "deny",
            "allowed": "allow",
            "allowed-skill": "allow",
        })
        self.assertNotIn("excluded", rules)


if __name__ == "__main__":
    unittest.main()
