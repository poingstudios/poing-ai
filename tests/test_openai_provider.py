import json
import unittest
from unittest.mock import MagicMock, patch

from poing_ai.ai.openai_compatible import OpenAICompatibleProvider, sanitize_ai_json_output
from poing_ai.core.models import ReviewVerdict, TriagePriority


class TestOpenAIProvider(unittest.TestCase):
    def setUp(self):
        self.provider = OpenAICompatibleProvider(
            api_key="test_key",
            base_url="https://api.deepseek.com/v1",
            models_to_try=["deepseek-chat"],
        )

    def test_sanitize_ai_json_output(self):
        raw = "<think>reasoning details here</think>```json\n{\"test\": 123}\n```"
        cleaned = sanitize_ai_json_output(raw)
        self.assertEqual(cleaned, '{"test": 123}')

    @patch("requests.post")
    def test_generate_review(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "verdict": "APPROVED",
                            "summary": "Clean code changes.",
                            "findings": [],
                            "comments": [],
                        })
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        result = self.provider.generate_review("Review diff")
        self.assertIsNotNone(result)
        self.assertEqual(result.verdict, ReviewVerdict.APPROVED)
        self.assertEqual(result.summary, "Clean code changes.")

    @patch("requests.post")
    def test_generate_triage(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "labels": ["enhancement"],
                            "priority": "low",
                            "summary": "Add new dark theme",
                            "is_duplicate": False,
                        })
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        result = self.provider.generate_triage("Triage issue")
        self.assertIsNotNone(result)
        self.assertEqual(result.priority, TriagePriority.LOW)
        self.assertIn("enhancement", result.labels)


if __name__ == "__main__":
    unittest.main()
