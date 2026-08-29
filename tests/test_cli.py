import unittest
from unittest.mock import MagicMock, patch

from poing_reviewer.cli import create_parser, main
from poing_reviewer.core.models import ReviewResult, ReviewVerdict, TriagePriority, TriageResult


class TestCLI(unittest.TestCase):
    def test_parser_arguments(self):
        parser = create_parser()
        args = parser.parse_args([
            "--local",
            "--provider", "ollama",
            "--model", "deepseek-r1:latest",
            "--api-base", "http://localhost:11434",
            "--staged",
            "--output", "json",
            "--fail-on-changes",
        ])
        self.assertTrue(args.local)
        self.assertEqual(args.provider, "ollama")
        self.assertEqual(args.model, "deepseek-r1:latest")
        self.assertEqual(args.api_base, "http://localhost:11434")
        self.assertTrue(args.staged)
        self.assertEqual(args.output, "json")
        self.assertTrue(args.fail_on_changes)

    @patch("poing_reviewer.services.review_service.ReviewService.run")
    def test_main_review_success(self, mock_review_run):
        mock_review_run.return_value = ReviewResult(
            verdict=ReviewVerdict.APPROVED,
            summary="Clean changes",
        )
        exit_code = main(["--local", "--provider", "gemini"])
        self.assertEqual(exit_code, 0)

    @patch("poing_reviewer.services.review_service.ReviewService.run")
    def test_main_fail_on_changes(self, mock_review_run):
        mock_review_run.return_value = ReviewResult(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Bug found",
        )
        exit_code = main(["--local", "--fail-on-changes"])
        self.assertEqual(exit_code, 1)

    @patch("poing_reviewer.services.triage_service.TriageService.run")
    def test_main_triage(self, mock_triage_run):
        mock_triage_run.return_value = TriageResult(
            labels=["bug"],
            priority=TriagePriority.HIGH,
            summary="Crash",
        )
        exit_code = main(["--mode", "triage", "--local", "--issue-title", "Bug", "--issue-body", "Details"])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
