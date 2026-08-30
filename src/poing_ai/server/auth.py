# Copyright 2026 Poing Studios
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import hashlib
import hmac
import time
from typing import Optional
import requests

from poing_ai.core.logging import get_logger

logger = get_logger("server.auth")


def verify_webhook_signature(payload: bytes, signature_header: Optional[str], secret: str) -> bool:
    """Verifies the GitHub webhook HMAC-SHA256 signature."""
    if not secret:
        # If no secret is configured, accept (useful for development)
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_sig = signature_header.split("sha256=")[1]
    computed_sig = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, computed_sig)


def generate_app_jwt(app_id: str, private_key_pem: str) -> str:
    """Generates a GitHub App RS256 JWT valid for 10 minutes."""
    import jwt
    now = int(time.time())
    payload = {
        "iat": now - 60,  # Issued 1 minute in the past for clock drift
        "exp": now + (10 * 60),  # Expires in 10 minutes
        "iss": str(app_id),
    }
    encoded_jwt = jwt.encode(payload, private_key_pem, algorithm="RS256")
    return encoded_jwt if isinstance(encoded_jwt, str) else encoded_jwt.decode("utf-8")


def get_installation_token(app_id: str, private_key_pem: str, installation_id: int) -> Optional[str]:
    """Exchanges GitHub App JWT for a repository installation token."""
    try:
        app_jwt = generate_app_jwt(app_id, private_key_pem)
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = requests.post(url, headers=headers, timeout=15)
        if resp.status_code == 201:
            return resp.json().get("token")
        logger.error(f"Failed to obtain installation token ({resp.status_code}): {resp.text}")
    except Exception as e:
        logger.error(f"Error requesting installation token: {e}")

    return None

