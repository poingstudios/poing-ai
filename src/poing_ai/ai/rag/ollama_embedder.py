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

logger = get_logger("ai.rag.ollama_embedder")

DEFAULT_OLLAMA_EMBEDDING_MODELS = [
    "nomic-embed-text",
    "all-minilm",
    "bge-m3",
    "mxbai-embed-large",
]


class OllamaEmbedder(BaseEmbedder):
    """Generates vector embeddings using local Ollama instance."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        primary_model: str = "nomic-embed-text",
        fallback_models: Optional[List[str]] = None,
    ):
        raw_base = base_url or "http://localhost:11434"
        self.base_url = raw_base.rstrip("/").removesuffix("/v1").removesuffix("/api")
        models = [primary_model] + (fallback_models or DEFAULT_OLLAMA_EMBEDDING_MODELS)
        seen = set()
        self.models_to_try = [m for m in models if not (m in seen or seen.add(m))]

    def _get_available_models(self) -> List[str]:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                installed = {m.get("name", "").split(":")[0] for m in data.get("models", [])}
                # Return configured models that match installed model names
                return [m for m in self.models_to_try if m.split(":")[0] in installed]
        except Exception:
            pass
        return []

    def embed_text(self, text: str) -> List[float]:
        if not text.strip():
            return []

        available_models = self._get_available_models()
        if not available_models:
            return []

        for model in available_models:
            # Try Ollama /api/embeddings first
            url = f"{self.base_url}/api/embeddings"
            payload: Dict[str, Any] = {
                "model": model,
                "prompt": text[:4000],
            }

            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    embedding = data.get("embedding", [])
                    if embedding:
                        return embedding
            except Exception:
                pass

            # Also try Ollama /api/embed (newer API format)
            embed_url = f"{self.base_url}/api/embed"
            embed_payload = {
                "model": model,
                "input": text[:4000],
            }
            try:
                resp = requests.post(embed_url, json=embed_payload, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    embeddings = data.get("embeddings", [])
                    if embeddings and len(embeddings) > 0:
                        return embeddings[0]
            except Exception:
                pass

        return []
