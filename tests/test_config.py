import unittest
from poing_ai.core.config import Config, build_model_list, fingerprint, parse_repo


class TestConfig(unittest.TestCase):
    def test_parse_repo(self):
        owner, repo = parse_repo("poingstudios/godot-admob-plugin")
        self.assertEqual(owner, "poingstudios")
        self.assertEqual(repo, "godot-admob-plugin")

        owner, repo = parse_repo("invalid_format")
        self.assertEqual(owner, "")
        self.assertEqual(repo, "")

    def test_fingerprint(self):
        fp1 = fingerprint("src/main.gd", "Null pointer bug", line=42)
        fp2 = fingerprint("src/main.gd", "Null pointer bug", line=42)
        fp3 = fingerprint("src/main.gd", "Different bug", line=42)
        self.assertEqual(fp1, fp2)
        self.assertNotEqual(fp1, fp3)

    def test_build_model_list(self):
        models = build_model_list("custom-model", "fallback-1, fallback-2")
        self.assertEqual(models[0], "custom-model")
        self.assertIn("fallback-1", models)
        self.assertIn("fallback-2", models)
        self.assertIn("gemini-3.5-flash", models)

    def test_config_initialization(self):
        cfg = Config(
            mode="triage",
            gemini_api_key="test_key",
            repo="poingstudios/test-repo",
            issue_number="123",
            local=True,
        )
        self.assertEqual(cfg.MODE, "triage")
        self.assertEqual(cfg.GEMINI_API_KEY, "test_key")
        self.assertEqual(cfg.owner, "poingstudios")
        self.assertEqual(cfg.repo_name, "test-repo")
        self.assertEqual(cfg.ISSUE_NUMBER, "123")
        self.assertTrue(cfg.LOCAL)


if __name__ == "__main__":
    unittest.main()
