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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RetrievedDocument:
    source: str
    content: str
    score: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


class BaseRetriever(ABC):
    """Abstract interface for RAG context retrieval."""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedDocument]:
        """Retrieve relevant context documents for a query."""
        pass


class BaseEmbedder(ABC):
    """Abstract interface for embedding generation."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate vector embedding for text."""
        pass
