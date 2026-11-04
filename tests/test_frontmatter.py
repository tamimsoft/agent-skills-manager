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

    def test_bom_before_frontmatter(self):
        r = parse_frontmatter("\ufeff---\nname: foo\ndescription: bar\n---\n")
        self.assertEqual(r["status"], "valid")
        self.assertEqual(r["data"]["name"], "foo")

    def test_hash_inside_quoted_value_is_not_a_comment(self):
        r = parse_frontmatter(
            '---\nname: "foo"\ndescription: "a # value" # trailing comment\n---\n'
        )
        self.assertEqual(r["data"]["description"], "a # value")

    def test_multiline_plain_scalar_is_folded(self):
        r = parse_frontmatter(
            "---\nname: foo\ndescription: first line\n  second line\n---\n"
        )
        self.assertEqual(r["data"]["description"], "first line second line")

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
        text = "---\nname: foo\ndescription: bar\nbad key: value\n---\n"
        r = parse_frontmatter(text)
        self.assertTrue(any("unsupported-yaml" in w for w in r["warnings"]))


if __name__ == "__main__":
    unittest.main()