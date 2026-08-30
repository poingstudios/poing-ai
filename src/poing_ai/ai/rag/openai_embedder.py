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

from typing import Any, Dict, List, Optional
import requests

from poing_ai.ai.rag.base import BaseEmbedder
from poing_ai.core.logging import get_logger

logger = get_logger("ai.rag.openai_embedder")

DEFAULT_OPENAI_EMBEDDING_MODELS = [
    "text-embedding-3-small",
    "text-embedding-ada-002",
    "text-embedding-3-large",
]


class OpenAIEmbedder(BaseEmbedder):
    """Generates vector embeddings using OpenAI or compatible API endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        primary_model: str = "text-embedding-3-small",
        fallback_models: Optional[List[str]] = None,
    ):
        self.api_key = api_key or "dummy"
        base = (base_url or "https://api.openai.com/v1").rstrip("/")
        if not base.endswith("/v1") and not base.endswith("/embeddings"):
            base = f"{base}/v1"
        self.base_url = base
        models = [primary_model] + (fallback_models or DEFAULT_OPENAI_EMBEDDING_MODELS)
        seen = set()
        self.models_to_try = [m for m in models if not (m in seen or seen.add(m))]

    def embed_text(self, text: str) -> List[float]:
        if not text.strip():
            return []

        url = f"{self.base_url}/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        for model in self.models_to_try:
            payload: Dict[str, Any] = {
                "model": model,
                "input": text[:8000],
            }
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", [])
                    if items and "embedding" in items[0]:
                        return items[0]["embedding"]
            except Exception as e:
                logger.warning(f"OpenAI embedding request failed for {model}: {e}")

        return []
