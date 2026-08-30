import unittest
from poing_ai.ai.false_positive import (
    add_footer_hint,
    fetch_thumbs_down_fingerprints,
    filter_action_version_false_positives,
    filter_speculative_false_positives,
    strip_footer,
)
from poing_ai.core.models import ReviewComment, ReviewFinding


class TestFalsePositive(unittest.TestCase):
    def test_footer_hint(self):
        body = "Review comment body"
        with_footer = add_footer_hint(body)
        self.assertIn("👍 helpful", with_footer)
        stripped = strip_footer(with_footer)
        self.assertEqual(stripped, body)

    def test_fetch_thumbs_down(self):
        threads = [
            {
                "path": "test.gd",
                "line": 15,
                "comments": {
                    "nodes": [
                        {
                            "author": {"login": "poing-ai[bot]"},
                            "body": "False positive comment\n\n---\n> 👍 helpful · 👎 false positive",
                            "reactions": {"nodes": [{"content": "THUMBS_DOWN"}]},
                        }
                    ]
                },
            }
        ]
        suppressed = fetch_thumbs_down_fingerprints(threads, bot_login="poing-ai[bot]")
        self.assertEqual(len(suppressed), 1)

    def test_fetch_thumbs_down_with_none_author(self):
        threads = [
            {
                "path": "test.gd",
                "line": 15,
                "comments": {
                    "nodes": [
                        {
                            "author": None,
                            "body": "Comment from deleted user\n\n---\n> 👍 helpful · 👎 false positive",
                            "reactions": {"nodes": [{"content": "THUMBS_DOWN"}]},
                        },
                        {
                            "author": {"login": None},
                            "body": "Comment from anonymous user",
                            "reactions": {"nodes": [{"content": "THUMBS_DOWN"}]},
                        },
                    ]
                },
            }
        ]
        suppressed = fetch_thumbs_down_fingerprints(threads, bot_login="poing-ai[bot]")
        self.assertEqual(len(suppressed), 1)

    def test_filter_speculative(self):
        findings = [
            ReviewFinding(severity="🟡", file="test.gd", finding="Please ensure other parts of the file call this safely."),
            ReviewFinding(severity="🔴", file="test.gd", finding="Definite null pointer dereference here."),
        ]
        comments = [
            ReviewComment(path="test.gd", line=10, body="Check if other places handle this."),
            ReviewComment(path="test.gd", line=20, body="Variable undefined on line 20."),
        ]

        filtered_findings, filtered_comments = filter_speculative_false_positives(findings, comments)
        self.assertEqual(len(filtered_findings), 1)
        self.assertEqual(filtered_findings[0].severity, "🔴")
        self.assertEqual(len(filtered_comments), 1)
        self.assertEqual(filtered_comments[0].line, 20)


if __name__ == "__main__":
    unittest.main()
