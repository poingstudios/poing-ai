import unittest
from unittest.mock import MagicMock, patch
from poing_ai.ai.gemini import GeminiProvider
from poing_ai.core.models import ReviewVerdict, TriagePriority


class TestGeminiProvider(unittest.TestCase):
    def test_gemini_provider_generate_review(self):
        provider = GeminiProvider(api_key="mock_key", models_to_try=["gemini-3.5-flash"])

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"verdict": "APPROVED", "summary": "Looks good!", "findings": [], "comments": []}'
                            }
                        ]
                    }
                }
            ]
        }

        with patch("requests.post", return_value=mock_response):
            result = provider.generate_review("Prompt text")
            self.assertIsNotNone(result)
            self.assertEqual(result.verdict, ReviewVerdict.APPROVED)
            self.assertEqual(result.summary, "Looks good!")
            self.assertEqual(len(result.findings), 0)

    def test_gemini_provider_generate_triage(self):
        provider = GeminiProvider(api_key="mock_key", models_to_try=["gemini-3.5-flash"])

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"labels": ["bug", "android"], "priority": "high", "summary": "App crashes on launch", "is_duplicate": false}'
                            }
                        ]
                    }
                }
            ]
        }

        with patch("requests.post", return_value=mock_response):
            result = provider.generate_triage("Prompt text")
            self.assertIsNotNone(result)
            self.assertIn("bug", result.labels)
            self.assertEqual(result.priority, TriagePriority.HIGH)
            self.assertFalse(result.is_duplicate)


if __name__ == "__main__":
    unittest.main()
