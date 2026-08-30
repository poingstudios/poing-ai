import json
import unittest
from unittest.mock import MagicMock, patch

from poing_ai.ai.ollama import OllamaProvider
from poing_ai.core.models import ReviewVerdict, TriagePriority


class TestOllamaProvider(unittest.TestCase):
    def setUp(self):
        self.provider = OllamaProvider(
            base_url="http://localhost:11434",
            models_to_try=["deepseek-r1:latest"],
        )

    @patch("requests.get")
    def test_is_available(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        self.assertTrue(self.provider.is_available())

        mock_get.side_effect = Exception("Connection refused")
        self.assertFalse(self.provider.is_available())

    @patch("requests.post")
    def test_generate_review_with_reasoning_model(self, mock_post):
        # Simulating DeepSeek-R1 output with <think>...</think> reasoning tags
        deepseek_response = {
            "message": {
                "content": (
                    "<think>\nI am analyzing the diff for potential issues.\n"
                    "Found an unhandled exception in line 12.\n</think>\n"
                    "```json\n"
                    "{\n"
                    '  "verdict": "CHANGES_REQUESTED",\n'
                    '  "summary": "Fixes null reference bug.",\n'
                    '  "findings": [{"severity": "🔴", "file": "test.py", "finding": "Null dereference"}],\n'
                    '  "comments": [{"path": "test.py", "line": 12, "body": "Handle None value"}]\n'
                    "}\n"
                    "```"
                )
            }
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = deepseek_response
        mock_post.return_value = mock_resp

        result = self.provider.generate_review("Review this diff")
        self.assertIsNotNone(result)
        self.assertEqual(result.verdict, ReviewVerdict.CHANGES_REQUESTED)
        self.assertEqual(result.summary, "Fixes null reference bug.")
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].severity, "🔴")
        self.assertEqual(len(result.comments), 1)
        self.assertEqual(result.comments[0].line, 12)

    @patch("requests.post")
    def test_generate_triage(self, mock_post):
        triage_data = {
            "message": {
                "content": json.dumps({
                    "labels": ["bug", "ios"],
                    "priority": "high",
                    "summary": "Crash on iOS launch",
                    "is_duplicate": False,
                })
            }
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = triage_data
        mock_post.return_value = mock_resp

        result = self.provider.generate_triage("Triage this issue")
        self.assertIsNotNone(result)
        self.assertEqual(result.priority, TriagePriority.HIGH)
        self.assertIn("bug", result.labels)
        self.assertIn("ios", result.labels)
        self.assertFalse(result.is_duplicate)

    @patch("requests.post")
    def test_generate_changelog_summary(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "content": "<think>formatting notes</think>### Release Notes\n- Updated dependency to v2.0"
            }
        }
        mock_post.return_value = mock_resp

        notes = self.provider.generate_changelog_summary("Generate changelog")
        self.assertIsNotNone(notes)
        self.assertIn("### Release Notes", notes)
        self.assertNotIn("<think>", notes)

    @patch("requests.get")
    def test_get_installed_models(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "llama3:latest"},
                {"name": "deepseek-coder:6.7b"},
            ]
        }
        mock_get.return_value = mock_resp

        models = self.provider.get_installed_models()
        self.assertEqual(models, ["llama3:latest", "deepseek-coder:6.7b"])

    @patch("requests.get")
    def test_resolve_models_dynamic(self, mock_get):
        provider = OllamaProvider(base_url="http://localhost:11434")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "mistral:latest"},
                {"name": "deepseek-r1:latest"},
            ]
        }
        mock_get.return_value = mock_resp

        resolved = provider._resolve_models_to_try()
        # deepseek-r1 should be prioritized ahead of mistral
        self.assertEqual(resolved[0], "deepseek-r1:latest")
        self.assertEqual(resolved[1], "mistral:latest")


if __name__ == "__main__":
    unittest.main()
