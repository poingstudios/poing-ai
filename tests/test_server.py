import hashlib
import hmac
import unittest
from unittest.mock import MagicMock, patch

from poing_ai.server.auth import verify_webhook_signature

try:
    from fastapi.testclient import TestClient
    from poing_ai.server.app import app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


class TestServer(unittest.TestCase):
    def test_verify_webhook_signature(self):
        secret = "super_secret"
        payload = b'{"action": "opened"}'
        sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        self.assertTrue(verify_webhook_signature(payload, sig, secret))
        self.assertFalse(verify_webhook_signature(payload, "sha256=invalid", secret))
        self.assertFalse(verify_webhook_signature(payload, None, secret))

    @unittest.skipUnless(HAS_FASTAPI, "FastAPI not installed in local environment")
    def test_health_endpoint(self):
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "poing-ai"})

    @unittest.skipUnless(HAS_FASTAPI, "FastAPI not installed in local environment")
    @patch("poing_ai.server.app._handle_pull_request")
    @patch("poing_ai.server.app.get_installation_token")
    @patch.dict(
        "os.environ",
        {
            "APP_ID": "123456",
            "APP_PRIVATE_KEY": "mock_key",
            "WEBHOOK_SECRET": "secret123",
            "GEMINI_API_KEY": "gemini_mock",
        },
    )
    def test_webhook_pull_request(self, mock_get_token, mock_handle_pr):
        client = TestClient(app)
        mock_get_token.return_value = "ghs_installation_token_123"
        payload = {
            "action": "opened",
            "installation": {"id": 9999},
            "pull_request": {
                "number": 42,
                "title": "Fix memory leak",
                "base": {"ref": "master"},
                "head": {"sha": "abcdef123456"},
            },
            "repository": {"full_name": "poingstudios/conqueror"},
        }
        body = str(payload).replace("'", '"').encode("utf-8")
        sig = "sha256=" + hmac.new(b"secret123", body, hashlib.sha256).hexdigest()

        response = client.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(response.status_code, 202)
        mock_handle_pr.assert_called_once()


if __name__ == "__main__":
    unittest.main()

