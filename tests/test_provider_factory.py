import unittest
from unittest.mock import MagicMock, patch

from poing_ai.ai.factory import create_ai_provider
from poing_ai.ai.gemini import GeminiProvider
from poing_ai.ai.ollama import OllamaProvider
from poing_ai.ai.openai_compatible import OpenAICompatibleProvider
from poing_ai.ai.rag.factory import create_retriever
from poing_ai.ai.rag.gemini_embedder import GeminiEmbedder
from poing_ai.ai.rag.local_rag import LocalFileRetriever
from poing_ai.ai.rag.ollama_embedder import OllamaEmbedder
from poing_ai.ai.rag.openai_embedder import OpenAIEmbedder
from poing_ai.ai.rag.vector_rag import VectorRAGRetriever
from poing_ai.core.config import Config


class TestProviderFactory(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict("os.environ", {}, clear=True)
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    def test_explicit_ollama_provider(self):
        cfg = Config(provider="ollama", api_base="http://localhost:11434")
        provider = create_ai_provider(cfg)
        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider.base_url, "http://localhost:11434")

    def test_explicit_openai_provider(self):
        cfg = Config(provider="openai", api_key="sk-test", api_base="https://api.openai.com/v1")
        provider = create_ai_provider(cfg)
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.api_key, "sk-test")

    def test_explicit_gemini_provider(self):
        cfg = Config(provider="gemini", gemini_api_key="gemini-key")
        provider = create_ai_provider(cfg)
        self.assertIsInstance(provider, GeminiProvider)

    def test_auto_detect_gemini(self):
        cfg = Config(gemini_api_key="gemini-key")
        provider = create_ai_provider(cfg)
        self.assertIsInstance(provider, GeminiProvider)

    def test_auto_detect_openai(self):
        cfg = Config(openai_api_key="sk-test")
        provider = create_ai_provider(cfg)
        self.assertIsInstance(provider, OpenAICompatibleProvider)

    def test_auto_detect_deepseek(self):
        cfg = Config(deepseek_api_key="sk-deepseek")
        provider = create_ai_provider(cfg)
        self.assertIsInstance(provider, OpenAICompatibleProvider)

    def test_auto_detect_ollama_from_base_url(self):
        cfg = Config(api_base="http://localhost:11434")
        provider = create_ai_provider(cfg)
        self.assertIsInstance(provider, OllamaProvider)

    def test_auto_detect_local_default(self):
        cfg = Config(local=True)
        provider = create_ai_provider(cfg)
        self.assertIsInstance(provider, OllamaProvider)

    def test_rag_factory_gemini(self):
        cfg = Config(gemini_api_key="gemini-key")
        retriever = create_retriever(cfg)
        self.assertIsInstance(retriever, VectorRAGRetriever)
        self.assertIsInstance(retriever.embedder, GeminiEmbedder)

    def test_rag_factory_ollama(self):
        cfg = Config(provider="ollama", api_base="http://localhost:11434")
        retriever = create_retriever(cfg)
        self.assertIsInstance(retriever, VectorRAGRetriever)
        self.assertIsInstance(retriever.embedder, OllamaEmbedder)

    def test_rag_factory_openai(self):
        cfg = Config(openai_api_key="sk-test")
        retriever = create_retriever(cfg)
        self.assertIsInstance(retriever, VectorRAGRetriever)
        self.assertIsInstance(retriever.embedder, OpenAIEmbedder)

    def test_rag_factory_local_fallback(self):
        cfg = Config(local=True)
        retriever = create_retriever(cfg)
        self.assertIsInstance(retriever, LocalFileRetriever)


if __name__ == "__main__":
    unittest.main()
