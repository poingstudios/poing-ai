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
from typing import Optional

from poing_reviewer.ai.rag.base import BaseRetriever
from poing_reviewer.ai.rag.gemini_embedder import GeminiEmbedder
from poing_reviewer.ai.rag.local_rag import LocalFileRetriever
from poing_reviewer.ai.rag.ollama_embedder import OllamaEmbedder
from poing_reviewer.ai.rag.openai_embedder import OpenAIEmbedder
from poing_reviewer.ai.rag.vector_rag import VectorRAGRetriever
from poing_reviewer.core.config import Config
from poing_reviewer.core.logging import get_logger

logger = get_logger("ai.rag.factory")


def create_retriever(config: Config, root_dir: Optional[Path] = None) -> BaseRetriever:
    """Instantiates the appropriate RAG context retriever based on configuration."""
    base_dir = root_dir or Path.cwd()
    provider_name = (config.PROVIDER or "").lower().strip()

    if config.GEMINI_API_KEY:
        logger.info("Using Vector RAG with GeminiEmbedder")
        return VectorRAGRetriever(
            embedder=GeminiEmbedder(api_key=config.GEMINI_API_KEY),
            root_dir=base_dir,
        )

    if provider_name == "ollama" or (config.API_BASE and "11434" in config.API_BASE):
        logger.info("Using Vector RAG with OllamaEmbedder")
        return VectorRAGRetriever(
            embedder=OllamaEmbedder(base_url=config.API_BASE),
            root_dir=base_dir,
        )

    if config.OPENAI_API_KEY:
        logger.info("Using Vector RAG with OpenAIEmbedder")
        return VectorRAGRetriever(
            embedder=OpenAIEmbedder(
                api_key=config.OPENAI_API_KEY,
                base_url=config.API_BASE,
            ),
            root_dir=base_dir,
        )

    logger.info("Using LocalFileRetriever (Markdown file scanner)")
    return LocalFileRetriever(root_dir=base_dir)
