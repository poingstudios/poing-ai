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

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from poing_ai.ai.rag.base import BaseEmbedder, BaseRetriever, RetrievedDocument
from poing_ai.ai.rag.markdown_parser import parse_markdown_with_breadcrumbs
from poing_ai.core.logging import get_logger

logger = get_logger("ai.rag.vector")


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a, b in zip(vec_a, vec_a)))
    norm_b = math.sqrt(sum(b * b for a, b in zip(vec_b, vec_b)))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorRAGRetriever(BaseRetriever):
    """Semantic vector retriever using vector embeddings and cosine similarity."""

    def __init__(
        self,
        embedder: BaseEmbedder,
        root_dir: Optional[Path] = None,
        guidelines_dirs: Optional[List[str]] = None,
    ):
        self.embedder = embedder
        self.root_dir = root_dir or Path.cwd()
        self.guidelines_dirs = guidelines_dirs or ["docs", ".agents", "guidelines", "rules"]
        self._index: List[Tuple[RetrievedDocument, List[float]]] = []
        self._indexed = False

    def _build_index(self) -> None:
        candidate_paths = [
            self.root_dir / "AGENTS.md",
            self.root_dir / ".github" / "AGENTS.md",
            self.root_dir / "CONTRIBUTING.md",
            self.root_dir / ".github" / "CONTRIBUTING.md",
            self.root_dir / "GEMINI.md",
            self.root_dir / "CLAUDE.md",
        ]

        # Search configured guidelines directories
        for sub_dir in self.guidelines_dirs:
            dpath = self.root_dir / sub_dir
            if dpath.exists() and dpath.is_dir():
                for md_file in list(dpath.glob("**/*.md"))[:20]:
                    if md_file not in candidate_paths:
                        candidate_paths.append(md_file)

        existing_paths = [p for p in candidate_paths if p.exists() and p.is_file()]
        logger.info(f"Building vector index for {len(existing_paths)} documentation and guideline file(s)...")

        for path in existing_paths:
            try:
                content = path.read_text(encoding="utf-8", errors="replace").strip()
                if not content:
                    continue
                rel_source = str(path.relative_to(self.root_dir) if path.is_relative_to(self.root_dir) else path)
                sections = parse_markdown_with_breadcrumbs(rel_source, content)

                for sec in sections:
                    emb = self.embedder.embed_text(sec.content)
                    if emb:
                        doc = RetrievedDocument(
                            source=sec.breadcrumb,
                            content=sec.content,
                            score=1.0,
                        )
                        self._index.append((doc, emb))
            except Exception as e:
                logger.warning(f"Error indexing doc file {path}: {e}")

        self._indexed = True
        if self._index:
            dims = len(self._index[0][1])
            logger.info(f"✅ Vector index built: {len(self._index)} chunk(s) indexed ({dims}-dim embeddings).")
        else:
            logger.info("ℹ️ Vector index empty; falling back to direct document scanning.")

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedDocument]:
        if not self._indexed:
            self._build_index()

        if not self._index:
            return []

        logger.info(f"Querying vector index for relevant guidelines...")
        query_emb = self.embedder.embed_text(query)
        if not query_emb:
            logger.info("Query embedding failed; using top indexed sections.")
            return [doc for doc, _ in self._index[:top_k]]

        scored: List[Tuple[float, RetrievedDocument]] = []
        for doc, emb in self._index:
            score = cosine_similarity(query_emb, emb)
            doc_with_score = RetrievedDocument(
                source=doc.source,
                content=doc.content,
                score=round(score, 4),
                metadata=doc.metadata,
            )
            scored.append((score, doc_with_score))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [doc for _, doc in scored[:top_k]]
        if results:
            logger.info(f"✅ Vector RAG matched {len(results)} relevant section(s) (top similarity: {results[0].score}).")
        return results
