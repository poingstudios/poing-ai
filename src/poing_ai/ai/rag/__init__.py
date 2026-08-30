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

from poing_ai.ai.rag.base import BaseEmbedder, BaseRetriever, RetrievedDocument
from poing_ai.ai.rag.factory import create_retriever
from poing_ai.ai.rag.gemini_embedder import GeminiEmbedder
from poing_ai.ai.rag.local_rag import LocalFileRetriever
from poing_ai.ai.rag.ollama_embedder import OllamaEmbedder
from poing_ai.ai.rag.openai_embedder import OpenAIEmbedder
from poing_ai.ai.rag.symbol_impact import SymbolImpactRetriever
from poing_ai.ai.rag.test_pairing import TestPairingRetriever
from poing_ai.ai.rag.vector_rag import VectorRAGRetriever

__all__ = [
    "BaseRetriever",
    "BaseEmbedder",
    "RetrievedDocument",
    "GeminiEmbedder",
    "LocalFileRetriever",
    "OllamaEmbedder",
    "OpenAIEmbedder",
    "SymbolImpactRetriever",
    "TestPairingRetriever",
    "VectorRAGRetriever",
    "create_retriever",
]
