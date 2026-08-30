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
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from poing_ai.core.logging import get_logger

logger = get_logger("ai.rag.cache")

CACHE_VERSION = "1.0"


def compute_content_hash(text: str, model_name: str = "") -> str:
    """Computes a SHA-256 hash for text chunk and model name."""
    raw = f"{model_name}:{text.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class EmbeddingsCache:
    """Persists vector embeddings to disk using SHA-256 content hashes."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or (Path.cwd() / ".poing" / "cache")
        self.cache_file = self.cache_dir / "embeddings.json"
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self.cache_file.exists():
            return
        try:
            raw_data = self.cache_file.read_text(encoding="utf-8", errors="replace")
            if not raw_data.strip():
                return
            data = json.loads(raw_data)
            if isinstance(data, dict) and data.get("version") == CACHE_VERSION:
                self._entries = data.get("entries", {})
        except Exception as e:
            logger.warning(f"Failed to load embeddings cache from {self.cache_file}: {e}")
            self._entries = {}

    def get(self, content_hash: str) -> Optional[List[float]]:
        """Returns cached embedding vector if present."""
        entry = self._entries.get(content_hash)
        if entry and isinstance(entry, dict):
            embedding = entry.get("embedding")
            if isinstance(embedding, list) and embedding:
                return embedding
        return None

    def set(self, content_hash: str, embedding: List[float], source: str = "") -> None:
        """Stores embedding vector in cache."""
        if not content_hash or not embedding:
            return
        self._entries[content_hash] = {
            "source": source,
            "embedding": embedding,
            "updated_at": int(time.time()),
        }
        self._dirty = True

    def save(self) -> None:
        """Flushes cache entries to disk."""
        if not self._dirty:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": CACHE_VERSION,
                "entries": self._entries,
            }
            tmp_file = self.cache_dir / "embeddings.json.tmp"
            tmp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_file.replace(self.cache_file)
            self._dirty = False
            logger.info(f"💾 Embeddings cache saved to {self.cache_file} ({len(self._entries)} entries).")
        except Exception as e:
            logger.warning(f"Failed to save embeddings cache to {self.cache_file}: {e}")
