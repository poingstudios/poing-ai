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

import time
from typing import Any, Dict, List, Optional
import requests

from poing_reviewer.ai.rag.base import BaseEmbedder
from poing_reviewer.core.logging import get_logger

logger = get_logger("ai.rag.gemini_embedder")

EMBEDDING_API_VERSIONS = ["v1beta"]

FALLBACK_EMBEDDING_MODELS = [
    "gemini-embedding-2-preview",
    "gemini-embedding-001",
]


class GeminiEmbedder(BaseEmbedder):
    """Generates vector embeddings using Google Gemini Embedding API with fallbacks."""

    def __init__(
        self,
        api_key: str,
        primary_model: str = "gemini-embedding-2-preview",
        fallback_models: Optional[List[str]] = None,
    ):
        self.api_key = api_key
        models = [primary_model] + (fallback_models or FALLBACK_EMBEDDING_MODELS)
        seen = set()
        self.models_to_try = [m for m in models if not (m in seen or seen.add(m))]

    def embed_text(self, text: str) -> List[float]:
        if not self.api_key or not text.strip():
            return []

        for api_ver in EMBEDDING_API_VERSIONS:
            for model in self.models_to_try:
                url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:embedContent?key={self.api_key}"
                payload: Dict[str, Any] = {
                    "content": {
                        "parts": [{"text": text[:8000]}]
                    },
                }

                for attempt in range(3):
                    try:
                        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
                        if resp.status_code == 200:
                            data = resp.json()
                            embedding = data.get("embedding", {}).get("values", [])
                            if embedding:
                                return embedding

                        if resp.status_code in (429, 503) and attempt < 2:
                            time.sleep(2 ** attempt * 2)
                            continue

                        logger.warning(f"Embedding API error ({model}): {resp.status_code} {resp.text[:150]}")
                        break
                    except Exception as e:
                        logger.warning(f"Embedding request failed for {model}: {e}")
                        if attempt < 2:
                            time.sleep(2 ** attempt * 2)
                            continue
                        break

        return []
