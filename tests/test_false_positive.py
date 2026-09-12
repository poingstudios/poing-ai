import sys
from pathlib import Path
import unittest

src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

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

    def test_thumbs_down_location_suppression_different_wording(self):
        from poing_ai.ai.false_positive import is_suppressed

        threads = [
            {
                "path": "test.gd",
                "line": 15,
                "comments": {
                    "nodes": [
                        {
                            "author": {"login": "poing-ai[bot]"},
                            "body": "actions/create-github-app-token requires app-id parameter",
                            "reactions": {"nodes": [{"content": "THUMBS_DOWN"}]},
                        }
                    ]
                },
            }
        ]
        suppressed = fetch_thumbs_down_fingerprints(threads, bot_login="poing-ai[bot]")

        # Different wording on the same line should be suppressed
        self.assertTrue(
            is_suppressed(
                "actions/create-github-app-token expects the required parameter app-id",
                "test.gd",
                15,
                suppressed,
            )
        )

        # Different line should not be suppressed
        self.assertFalse(
            is_suppressed(
                "actions/create-github-app-token expects the required parameter app-id",
                "test.gd",
                99,
                suppressed,
            )
        )

    def test_thumbs_down_fuzzy_suppression_line_none(self):
        from poing_ai.ai.false_positive import is_suppressed

        threads = [
            {
                "path": "test.gd",
                "line": None,
                "comments": {
                    "nodes": [
                        {
                            "author": {"login": "poing-ai[bot]"},
                            "body": "actions/create-github-app-token requires app-id parameter here",
                            "reactions": {"nodes": [{"content": "THUMBS_DOWN"}]},
                        }
                    ]
                },
            }
        ]
        suppressed = fetch_thumbs_down_fingerprints(threads, bot_login="poing-ai[bot]")

        # Fuzzy matching should catch very similar reworded intent on the same file
        self.assertTrue(
            is_suppressed(
                "actions/create-github-app-token requires app-id parameter in this file",
                "test.gd",
                None,
                suppressed,
            )
        )

        # Completely unrelated comment should not be suppressed
        self.assertFalse(
            is_suppressed(
                "Variable foo is never initialized in function _ready()",
                "test.gd",
                None,
                suppressed,
            )
        )

    def test_filter_suppressed_findings(self):
        from poing_ai.ai.false_positive import filter_suppressed_findings

        findings = [
            ReviewFinding(severity="🔴", file="src/main.gd", finding="L15: Null pointer dereference"),
            ReviewFinding(severity="🟡", file="src/main.gd", finding="L42: Unused local variable"),
            ReviewFinding(severity="🔴", file="src/other.gd", finding="Line 15: Invalid type cast"),
        ]
        suppressed_locations = {("src/main.gd", 15)}
        filtered = filter_suppressed_findings(findings, suppressed_locations, suppressed_fps=set())

        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0].finding, "L42: Unused local variable")
        self.assertEqual(filtered[1].file, "src/other.gd")

    def test_filter_action_version_false_positive(self):
        findings = [
            ReviewFinding(severity="🔴", file=".github/workflows/ci.yml", finding="actions/checkout@v7 does not exist"),
            ReviewFinding(severity="🔴", file=".github/workflows/ci.yml", finding="actions/unknown@v1 is non-existent"),
        ]
        comments = [
            ReviewComment(path=".github/workflows/ci.yml", line=10, body="actions/checkout@v7 is an invalid version"),
        ]
        verified_actions = {
            "actions/checkout@v7": True,
            "actions/unknown@v1": False,
        }

        filtered_findings, filtered_comments = filter_action_version_false_positives(
            findings, comments, verified_actions
        )
        # actions/checkout@v7 is valid, so finding and comment for it are suppressed
        self.assertEqual(len(filtered_findings), 1)
        self.assertIn("actions/unknown@v1", filtered_findings[0].finding)
        self.assertEqual(len(filtered_comments), 0)

    def test_filter_action_input_schema_false_positive(self):
        from poing_ai.core.models import ActionInput, ActionSchema

        schema = ActionSchema(
            action_ref="actions/create-github-app-token@v3",
            exists=True,
            inputs={
                "client-id": ActionInput(name="client-id", required=False),
                "private-key": ActionInput(name="private-key", required=True),
                "app-id": ActionInput(name="app-id", deprecated=True),
            },
        )
        verified_actions = {"actions/create-github-app-token@v3": schema}

        findings = [
            # False positive: claims declared input 'client-id' does not exist
            ReviewFinding(
                severity="🔴",
                file=".github/workflows/poing-ai.yml",
                finding="actions/create-github-app-token does not support client-id",
            ),
            # True positive: claims undeclared input 'foo-bar' does not exist
            ReviewFinding(
                severity="🔴",
                file=".github/workflows/poing-ai.yml",
                finding="actions/create-github-app-token uses invalid input foo-bar",
            ),
        ]
        comments = [
            # False positive: claims 'client-id' is not a valid parameter
            ReviewComment(
                path=".github/workflows/poing-ai.yml",
                line=44,
                body="'client-id' is not a valid parameter for actions/create-github-app-token@v3. Use 'app-id' instead.",
            ),
            # Legitimate comment: required parameter private-key missing
            ReviewComment(
                path=".github/workflows/poing-ai.yml",
                line=45,
                body="actions/create-github-app-token requires private-key parameter.",
            ),
        ]

        filtered_findings, filtered_comments = filter_action_version_false_positives(
            findings, comments, verified_actions
        )

        self.assertEqual(len(filtered_findings), 1)
        self.assertIn("foo-bar", filtered_findings[0].finding)

        self.assertEqual(len(filtered_comments), 1)
        self.assertIn("requires private-key", filtered_comments[0].body)


if __name__ == "__main__":
    unittest.main()

