import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from poing_ai.ai.rag.gemini_embedder import GeminiEmbedder
from poing_ai.ai.rag.vector_rag import VectorRAGRetriever, cosine_similarity


class TestRAG(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cosine_similarity(self):
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        vec3 = [0.0, 1.0, 0.0]

        self.assertAlmostEqual(cosine_similarity(vec1, vec2), 1.0)
        self.assertAlmostEqual(cosine_similarity(vec1, vec3), 0.0)

    def test_gemini_embedder(self):
        embedder = GeminiEmbedder(api_key="mock_key")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "embedding": {
                "values": [0.1, 0.2, 0.3, 0.4]
            }
        }

        with patch("requests.post", return_value=mock_resp):
            emb = embedder.embed_text("Sample text")
            self.assertEqual(len(emb), 4)
            self.assertEqual(emb[0], 0.1)

    def test_vector_rag_retriever(self):
        (self.test_dir / "AGENTS.md").write_text("Use GDScript := operator for type inference.", encoding="utf-8")
        (self.test_dir / "CONTRIBUTING.md").write_text("Guidelines for making pull requests.", encoding="utf-8")

        mock_embedder = MagicMock()
        # Mock embedding return: vector matching query closer to AGENTS.md
        def mock_embed(text: str):
            if "GDScript" in text:
                return [1.0, 0.0, 0.0]
            if "Guidelines" in text:
                return [0.0, 1.0, 0.0]
            if "query_gdscript" in text:
                return [0.99, 0.01, 0.0]
            return [0.5, 0.5, 0.0]

        mock_embedder.embed_text.side_effect = mock_embed

        retriever = VectorRAGRetriever(embedder=mock_embedder, root_dir=self.test_dir)
        docs = retriever.retrieve("query_gdscript", top_k=1)
        self.assertEqual(len(docs), 1)
        self.assertIn("AGENTS.md", docs[0].source)
        self.assertGreater(docs[0].score, 0.9)


if __name__ == "__main__":
    unittest.main()
