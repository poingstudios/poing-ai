import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
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


if __name__ == "__main__":
    unittest.main()
