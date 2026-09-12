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

    def test_gemini_provider_default_models(self):
        provider = GeminiProvider(api_key="mock_key")
        self.assertEqual(provider.models_to_try[0], "gemini-3.8-flash")
        self.assertIn("gemini-3.7-flash", provider.models_to_try)

    def test_gemini_provider_parse_json_fallback_with_thinking_braces(self):
        provider = GeminiProvider(api_key="mock_key")
        # Text with thinking tags containing stray braces before the actual JSON payload
        raw_output = "<thought>Checking if {a: 1} is valid.</thought> Here is the output:\n{\"verdict\": \"APPROVED\", \"summary\": \"All good\", \"findings\": [], \"comments\": []}"
        parsed = provider._parse_json(raw_output)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("verdict"), "APPROVED")
        self.assertEqual(parsed.get("summary"), "All good")

    def test_gemini_provider_search_grounding_payload(self):
        provider_with_grounding = GeminiProvider(api_key="mock_key", enable_search_grounding=True)
        provider_without_grounding = GeminiProvider(api_key="mock_key", enable_search_grounding=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"verdict": "APPROVED", "summary": "Grounded review", "findings": [], "comments": []}'
                            }
                        ]
                    }
                }
            ]
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            provider_with_grounding.generate_review("Prompt text")
            self.assertTrue(mock_post.called)
            sent_payload = mock_post.call_args[1]["json"]
            self.assertIn("tools", sent_payload)
            self.assertEqual(sent_payload["tools"], [{"google_search": {}}])
            # Must NOT combine tools with responseMimeType
            self.assertNotIn("responseMimeType", sent_payload.get("generationConfig", {}))

        with patch("requests.post", return_value=mock_response) as mock_post:
            provider_without_grounding.generate_review("Prompt text")
            self.assertTrue(mock_post.called)
            sent_payload = mock_post.call_args[1]["json"]
            self.assertNotIn("tools", sent_payload)
            self.assertEqual(sent_payload.get("generationConfig", {}).get("responseMimeType"), "application/json")

    def test_gemini_provider_search_grounding_fallback_on_error(self):
        provider = GeminiProvider(api_key="mock_key", enable_search_grounding=True, models_to_try=["gemini-2.5-flash"])

        mock_err_400 = MagicMock()
        mock_err_400.status_code = 400
        mock_err_400.text = "Tool use with response mime type is unsupported"

        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"verdict": "APPROVED", "summary": "Fallback worked!", "findings": [], "comments": []}'
                            }
                        ]
                    }
                }
            ]
        }

        # First call fails with 400 (grounding error), second call retries without tools and succeeds
        with patch("requests.post", side_effect=[mock_err_400, mock_ok]) as mock_post:
            result = provider.generate_review("Prompt text")
            self.assertEqual(mock_post.call_count, 2)
            # Second call must not contain tools
            second_payload = mock_post.call_args_list[1][1]["json"]
            self.assertNotIn("tools", second_payload)
            self.assertIsNotNone(result)
            self.assertEqual(result.summary, "Fallback worked!")


if __name__ == "__main__":
    unittest.main()

