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

from poing_reviewer.ai.rag.base import BaseRetriever, RetrievedDocument
from poing_reviewer.core.logging import get_logger

logger = get_logger("ai.rag.local")


class LocalFileRetriever(BaseRetriever):
    """Retrieves repository documentation and guidelines from local markdown files."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path.cwd()

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedDocument]:
        docs: List[RetrievedDocument] = []
        candidate_paths = [
            self.root_dir / "AGENTS.md",
            self.root_dir / ".github" / "AGENTS.md",
            self.root_dir / "CONTRIBUTING.md",
            self.root_dir / ".github" / "CONTRIBUTING.md",
        ]

        # Also search docs/ directory if present
        docs_dir = self.root_dir / "docs"
        if docs_dir.exists() and docs_dir.is_dir():
            for md_file in list(docs_dir.glob("**/*.md"))[:10]:
                candidate_paths.append(md_file)

        for path in candidate_paths:
            if path.exists() and path.is_file():
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    if content.strip():
                        docs.append(
                            RetrievedDocument(
                                source=str(path.relative_to(self.root_dir) if path.is_relative_to(self.root_dir) else path),
                                content=content[:8000],
                                score=1.0,
                            )
                        )
                except Exception as e:
                    logger.warning(f"Failed to read doc file {path}: {e}")

        return docs[:top_k]
