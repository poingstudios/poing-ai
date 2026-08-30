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

from pathlib import Path
from typing import List, Optional

from poing_ai.ai.rag.base import BaseRetriever, RetrievedDocument
from poing_ai.ai.rag.markdown_parser import parse_markdown_with_breadcrumbs
from poing_ai.core.logging import get_logger

logger = get_logger("ai.rag.local")


class LocalFileRetriever(BaseRetriever):
    """Retrieves repository documentation and guidelines from local markdown files using hierarchical AST breadcrumbs."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path.cwd()

    def retrieve(self, query: str, top_k: int = 6) -> List[RetrievedDocument]:
        candidate_paths = [
            self.root_dir / "AGENTS.md",
            self.root_dir / ".github" / "AGENTS.md",
            self.root_dir / "CONTRIBUTING.md",
            self.root_dir / ".github" / "CONTRIBUTING.md",
        ]

        # Also search docs/ and .agents/ directories if present
        for sub_dir in ["docs", ".agents"]:
            dpath = self.root_dir / sub_dir
            if dpath.exists() and dpath.is_dir():
                for md_file in list(dpath.glob("**/*.md"))[:15]:
                    candidate_paths.append(md_file)

        query_tokens = set(query.lower().split())
        scored_sections: List[tuple[float, RetrievedDocument]] = []

        for path in candidate_paths:
            if not (path.exists() and path.is_file()):
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                if not content.strip():
                    continue

                rel_name = str(path.relative_to(self.root_dir) if path.is_relative_to(self.root_dir) else path)
                sections = parse_markdown_with_breadcrumbs(rel_name, content)

                for sec in sections:
                    sec_lower = sec.content.lower()
                    sec_breadcrumb_lower = sec.breadcrumb.lower()

                    # Calculate match score based on token overlap in breadcrumb + content
                    matches = 0
                    for token in query_tokens:
                        if token in sec_breadcrumb_lower:
                            matches += 2  # Higher weight for matching header titles
                        elif token in sec_lower:
                            matches += 1

                    score = matches / max(1, len(query_tokens))
                    if score > 0 or len(sections) == 1:
                        doc = RetrievedDocument(
                            source=sec.breadcrumb,
                            content=sec.content,
                            score=score,
                        )
                        scored_sections.append((score, doc))
            except Exception as e:
                logger.warning(f"Failed to parse doc file {path}: {e}")

        if not scored_sections:
            return []

        # Sort by relevance score descending
        scored_sections.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored_sections[:top_k]]
