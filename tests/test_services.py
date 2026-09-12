import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from poing_ai.core.config import Config
from poing_ai.core.models import ReviewResult, ReviewVerdict, TriagePriority, TriageResult
from poing_ai.services.review_service import ReviewService
from poing_ai.services.triage_service import TriageService
from poing_ai.services.sync_service import SyncService


class TestServices(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_review_service_local(self):
        cfg = Config(mode="review", local=True, gemini_api_key="mock_key")
        mock_ai = MagicMock()
        mock_ai.generate_review.return_value = ReviewResult(
            verdict=ReviewVerdict.APPROVED,
            summary="Clean changes!",
            findings=[],
            comments=[],
        )

        service = ReviewService(config=cfg, ai_provider=mock_ai, root_dir=self.test_dir)
        result = service.run()
        self.assertEqual(result.verdict, ReviewVerdict.APPROVED)

    def test_triage_service_local(self):
        cfg = Config(
            mode="triage",
            local=True,
            issue_title="Bug in Android SDK",
            issue_body="NPE during initialization",
            gemini_api_key="mock_key",
        )
        mock_ai = MagicMock()
        mock_ai.generate_triage.return_value = TriageResult(
            labels=["bug", "android"],
            priority=TriagePriority.HIGH,
            summary="NPE during initialization",
            is_duplicate=False,
        )

        service = TriageService(config=cfg, ai_provider=mock_ai, root_dir=self.test_dir)
        result = service.run()
        self.assertIsNotNone(result)
        self.assertIn("bug", result.labels)
        self.assertEqual(result.priority, TriagePriority.HIGH)

    def test_sync_service(self):
        cfg = Config(mode="sync", local=True, dry_run=True)
        mock_ai = MagicMock()
        mock_ai.generate_changelog_summary.return_value = "Release Notes: Updated SDK to 23.0.0"

        service = SyncService(config=cfg, ai_provider=mock_ai, root_dir=self.test_dir)
        summary = service.run()
        self.assertEqual(len(summary.updates), 0)

    def test_sanitize_markdown_text(self):
        from poing_ai.services.review_service import _sanitize_markdown_text
        raw = '[src/main.py L42] Logic error.\\n\\nExample:\\npython\\nsha = run(["git"])\\n'
        cleaned = _sanitize_markdown_text(raw, strip_line_prefix=True)
        self.assertFalse(cleaned.startswith("[src/main.py L42]"))
        self.assertTrue(cleaned.startswith("Logic error."))
        self.assertNotIn("\\n", cleaned)
        self.assertIn("\n", cleaned)
        self.assertIn('run(["git"])', cleaned)

    def test_reevaluate_verdict(self):
        from poing_ai.services.review_service import reevaluate_verdict
        from poing_ai.core.models import ReviewComment, ReviewFinding

        # 1. CHANGES_REQUESTED with all findings and comments cleared -> APPROVED
        verdict = reevaluate_verdict(
            current_verdict=ReviewVerdict.CHANGES_REQUESTED,
            findings=[],
            comments=[],
        )
        self.assertEqual(verdict, ReviewVerdict.APPROVED)

        # 2. CHANGES_REQUESTED with only warnings/suggestions -> APPROVED_WITH_SUGGESTIONS
        verdict = reevaluate_verdict(
            current_verdict=ReviewVerdict.CHANGES_REQUESTED,
            findings=[ReviewFinding(severity="🟡", file="a.py", finding="Minor warning")],
            comments=[],
        )
        self.assertEqual(verdict, ReviewVerdict.APPROVED_WITH_SUGGESTIONS)

        # 3. CHANGES_REQUESTED with inline comments only -> APPROVED_WITH_SUGGESTIONS
        verdict = reevaluate_verdict(
            current_verdict=ReviewVerdict.CHANGES_REQUESTED,
            findings=[],
            comments=[ReviewComment(path="a.py", line=10, body="Suggestion")],
        )
        self.assertEqual(verdict, ReviewVerdict.APPROVED_WITH_SUGGESTIONS)

        # 4. CHANGES_REQUESTED with critical 🔴 finding -> remains CHANGES_REQUESTED
        verdict = reevaluate_verdict(
            current_verdict=ReviewVerdict.CHANGES_REQUESTED,
            findings=[ReviewFinding(severity="🔴", file="a.py", finding="Crash bug")],
            comments=[ReviewComment(path="a.py", line=10, body="Crash bug")],
        )
        self.assertEqual(verdict, ReviewVerdict.CHANGES_REQUESTED)

        # 5. APPROVED_WITH_SUGGESTIONS with all items cleared -> APPROVED
        verdict = reevaluate_verdict(
            current_verdict=ReviewVerdict.APPROVED_WITH_SUGGESTIONS,
            findings=[],
            comments=[],
        )
        self.assertEqual(verdict, ReviewVerdict.APPROVED)

    def test_review_service_pr_suppression_and_downgrade(self):
        from unittest.mock import patch
        from poing_ai.core.models import ReviewComment, ReviewFinding

        cfg = Config(
            mode="review",
            local=False,
            repo="poingstudios/test-repo",
            pr_number="123",
            github_token="fake_token",
            gemini_api_key="fake_key",
            dry_run=True,
        )
        mock_ai = MagicMock()
        mock_ai.generate_review.return_value = ReviewResult(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Found issues",
            findings=[
                ReviewFinding(severity="🔴", file="main.gd", finding="L15: Null pointer issue"),
            ],
            comments=[
                ReviewComment(path="main.gd", line=15, body="Null pointer issue on line 15"),
            ],
        )

        mock_client = MagicMock()
        mock_client.fetch_existing_reviews.return_value = []
        mock_client.resolve_pr_number.return_value = "123"
        # Thread 1 on main.gd:15 received 👎
        mock_client.fetch_review_threads.return_value = [
            {
                "id": "thread-1",
                "isResolved": False,
                "isOutdated": False,
                "path": "main.gd",
                "line": 15,
                "comments": {
                    "nodes": [
                        {
                            "databaseId": 101,
                            "author": {"login": "poing-ai[bot]"},
                            "body": "Null pointer issue with different wording",
                            "reactions": {"nodes": [{"content": "THUMBS_DOWN"}]},
                        }
                    ]
                },
            }
        ]

        diff_sample = (
            "diff --git a/main.gd b/main.gd\n"
            "index 0000000..1111111 100644\n"
            "--- a/main.gd\n"
            "+++ b/main.gd\n"
            "@@ -10,10 +10,10 @@\n"
            " line 10\n"
            " line 11\n"
            " line 12\n"
            " line 13\n"
            " line 14\n"
            "+line 15\n"
            " line 16\n"
            " line 17\n"
            " line 18\n"
            " line 19\n"
        )

        with patch("poing_ai.services.review_service.get_git_diff", return_value=diff_sample):
            service = ReviewService(
                config=cfg,
                ai_provider=mock_ai,
                github_client=mock_client,
                root_dir=self.test_dir,
            )
            result = service.run()

        # Both comment and finding on line 15 should be suppressed by thumbs-down,
        # and verdict should be downgraded to APPROVED!
        self.assertEqual(len(result.comments), 0)
        self.assertEqual(len(result.findings), 0)
        self.assertEqual(result.verdict, ReviewVerdict.APPROVED)


if __name__ == "__main__":
    unittest.main()
