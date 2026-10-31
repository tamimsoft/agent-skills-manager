import os
import tempfile
import unittest

from agent_skills.frontmatter import parse_frontmatter


class TestFrontmatter(unittest.TestCase):
    def test_valid(self):
        text = "---\nname: foo\ndescription: bar baz\n---\n\n# body\n"
        r = parse_frontmatter(text)
        self.assertEqual(r["status"], "valid")
        self.assertEqual(r["data"]["name"], "foo")
        self.assertEqual(r["data"]["description"], "bar baz")

    def test_missing(self):
        text = "# no frontmatter\n"
        r = parse_frontmatter(text)
        self.assertEqual(r["status"], "missing")
        self.assertEqual(r["data"], {})

    def test_malformed_unterminated(self):
        text = "---\nname: foo\n"
        r = parse_frontmatter(text)
        self.assertEqual(r["status"], "malformed")
        self.assertIsNotNone(r["error"])

    def test_quoted_values(self):
        text = '---\nname: "foo:bar"\ndescription: \'it works\'\n---\n'
        r = parse_frontmatter(text)
        self.assertEqual(r["status"], "valid")
        self.assertEqual(r["data"]["name"], "foo:bar")
        self.assertEqual(r["data"]["description"], "it works")

    def test_block_scalar_folded(self):
        text = "---\ndescription: >\n  line one\n  line two\n---\n"
        r = parse_frontmatter(text)
        self.assertIn("line one", r["data"]["description"])
        self.assertIn("line two", r["data"]["description"])

    def test_block_scalar_literal(self):
        text = "---\ndescription: |\n  line one\n  line two\n---\n"
        r = parse_frontmatter(text)
        self.assertEqual(r["data"]["description"], "line one\nline two")

    def test_partial(self):
        text = "---\nname: foo\n---\n"
        r = parse_frontmatter(text)
        self.assertEqual(r["status"], "partial")

    def test_value_with_colon(self):
        text = "---\ndescription: http://example.com:8080/path\n---\n"
        r = parse_frontmatter(text)
        self.assertEqual(r["data"]["description"], "http://example.com:8080/path")

    def test_unsupported_construct_warning(self):
        text = "---\nname: foo\ndescription: bar\n  bad indent\n---\n"
        r = parse_frontmatter(text)
        self.assertTrue(any("unsupported-yaml" in w for w in r["warnings"]))


if __name__ == "__main__":
    unittest.main()