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

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from poing_ai.ai.antigravity import AntigravityAgentProvider
from poing_ai.ai.prompts.fix import build_fix_prompt
from poing_ai.core.config import Config
from poing_ai.core.models import FileFix, FixResult
from poing_ai.services.fix_service import FixService


class TestFixService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.cfg = Config(local=True, provider="mock")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_fix_prompt(self):
        target_files = {"src/app.py": "def add(a, b):\n    return a - b\n"}
        prompt = build_fix_prompt(
            findings_context="Fix subtraction bug in add function",
            target_files=target_files,
            rag_guidelines="Use proper addition",
            engine_rules="Python standards",
            test_failure_trace="AssertionError: 2 != 0",
        )
        self.assertIn("Fix subtraction bug in add function", prompt)
        self.assertIn("def add(a, b):", prompt)
        self.assertIn("AssertionError: 2 != 0", prompt)
        self.assertIn("Use proper addition", prompt)

    def test_apply_patches(self):
        test_file = self.root_path / "calc.py"
        test_file.write_text("def subtract(a, b):\n    return a + b\n", encoding="utf-8")

        service = FixService(self.cfg)
        service.root_dir = self.root_path

        fixes = [
            FileFix(
                file_path="calc.py",
                explanation="Fix addition bug in subtract",
                original_snippet="return a + b",
                replacement_snippet="return a - b",
            )
        ]
        target_files = {"calc.py": test_file.read_text(encoding="utf-8")}
        applied, diffs = service._apply_patches(fixes, target_files)

        self.assertEqual(len(applied), 1)
        self.assertEqual(len(diffs), 1)
        self.assertIn("return a - b", test_file.read_text(encoding="utf-8"))

    def test_fix_service_run_success(self):
        test_file = self.root_path / "hello.py"
        test_file.write_text("print('Hello Wrold')\n", encoding="utf-8")

        mock_ai = MagicMock()
        mock_ai.generate_fix.return_value = FixResult(
            summary="Fixed typo in hello message",
            fixes=[
                FileFix(
                    file_path="hello.py",
                    explanation="Fix typo Wrold -> World",
                    original_snippet="Hello Wrold",
                    replacement_snippet="Hello World",
                )
            ],
            model="antigravity-preview-05-2026",
            tests_passed=True,
        )

        service = FixService(self.cfg, ai=mock_ai)
        service.root_dir = self.root_path

        with patch.object(service, "_run_test_validation", return_value=(True, "Tests OK")):
            result = service.run(
                findings_override="Typo in hello.py",
                target_files_override=["hello.py"],
            )

        self.assertIsNotNone(result)
        self.assertTrue(result.tests_passed)
        self.assertEqual(test_file.read_text(encoding="utf-8"), "print('Hello World')\n")

    def test_antigravity_agent_provider_json_extraction(self):
        provider = AntigravityAgentProvider(api_key="mock-key")
        raw_json = '```json\n{"summary": "Fixed bug", "fixes": [{"file_path": "a.py", "explanation": "fixed", "original_snippet": "foo", "replacement_snippet": "bar"}]}\n```'
        with patch.object(provider, "_call_agent", return_value=raw_json):
            fix_result = provider.generate_fix("prompt")

        self.assertIsNotNone(fix_result)
        self.assertEqual(fix_result.summary, "Fixed bug")
        self.assertEqual(len(fix_result.fixes), 1)
        self.assertEqual(fix_result.fixes[0].replacement_snippet, "bar")

    def test_discover_targets_from_issue(self):
        test_file = self.root_path / "src" / "math_utils.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def multiply(a, b): return a + b\n", encoding="utf-8")

        cfg = Config(
            local=True,
            provider="mock",
            issue_number="42",
            issue_title="Bug in src/math_utils.py multiplication",
            issue_body="The multiply function returns addition instead of multiplication.",
        )
        service = FixService(cfg)
        service.root_dir = self.root_path

        findings, files = service._discover_targets()
        self.assertIn("src/math_utils.py", files)
        self.assertIn("Bug in src/math_utils.py", findings)

    def test_discover_targets_from_issue_disabled_by_default_in_remote(self):
        cfg = Config(
            local=False,
            repo="poingstudios/test-repo",
            issue_number="42",
            issue_title="Bug in src/math_utils.py",
            issue_body="Broken function",
        )
        self.assertFalse(cfg.AUTO_WORK_ON_ISSUES)

        mock_client = MagicMock()
        mock_client.is_pull_request.return_value = False
        service = FixService(cfg, client=mock_client)
        service.root_dir = self.root_path

        findings, files = service._discover_targets()
        self.assertEqual(files, [])
        self.assertEqual(findings, "")

    def test_discover_targets_from_issue_explicit_command_proceeds(self):
        test_file = self.root_path / "src" / "math_utils.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def multiply(a, b): return a + b\n", encoding="utf-8")

        cfg = Config(
            local=False,
            repo="poingstudios/test-repo",
            issue_number="42",
            issue_title="Bug in src/math_utils.py",
            issue_body="Broken function",
        )
        cfg.COMMENT_BODY = "/fix please"

        mock_client = MagicMock()
        mock_client.is_pull_request.return_value = False
        service = FixService(cfg, client=mock_client)
        service.root_dir = self.root_path

        findings, files = service._discover_targets()
        self.assertIn("src/math_utils.py", files)

    def test_discover_targets_from_issue_with_opt_in_label(self):
        test_file = self.root_path / "src" / "math_utils.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def multiply(a, b): return a + b\n", encoding="utf-8")

        cfg = Config(
            local=False,
            repo="poingstudios/test-repo",
            issue_number="42",
        )
        mock_client = MagicMock()
        mock_client.is_pull_request.return_value = False
        mock_client.fetch_issue.return_value = {
            "title": "Bug in src/math_utils.py",
            "body": "Broken multiplication logic",
            "labels": [{"name": "auto-fix"}, {"name": "bug"}],
        }
        service = FixService(cfg, client=mock_client)
        service.root_dir = self.root_path

        findings, files = service._discover_targets()
        self.assertIn("src/math_utils.py", files)
        self.assertIn("Bug in src/math_utils.py", findings)

    def test_fix_service_token_clamping(self):
        test_file = self.root_path / "large_file.py"
        large_content = "x = 1\n" * 6000  # ~36,000 chars
        test_file.write_text(large_content, encoding="utf-8")

        mock_ai = MagicMock()
        mock_ai.generate_fix.return_value = FixResult(
            summary="Fixed large file",
            fixes=[
                FileFix(
                    file_path="large_file.py",
                    explanation="Fix line",
                    original_snippet="x = 1\n",
                    replacement_snippet="x = 2\n",
                )
            ],
            tests_passed=True,
        )

        mock_retriever = MagicMock()
        # Large RAG doc > 4000 chars
        large_doc = MagicMock()
        large_doc.source = "rules.md"
        large_doc.content = "A" * 4000
        mock_retriever.retrieve.return_value = [large_doc]

        service = FixService(self.cfg, ai=mock_ai, retriever=mock_retriever)
        service.root_dir = self.root_path

        with patch.object(service, "_run_test_validation", return_value=(True, "OK")):
            service.run(
                findings_override="Fix issue",
                target_files_override=["large_file.py"],
            )

        # Verify AI was called with clamped prompt
        mock_ai.generate_fix.assert_called_once()
        sent_prompt = mock_ai.generate_fix.call_args[0][0]
        self.assertIn("truncated remaining content to conserve quota", sent_prompt)
        self.assertIn("truncated guidelines", sent_prompt)

    def test_antigravity_agent_provider_failover(self):
        mock_fallback = MagicMock()
        mock_fallback.generate_fix.return_value = FixResult(
            summary="Fixed by fallback",
            fixes=[],
            model="gemini-3.8-flash",
        )
        provider = AntigravityAgentProvider(api_key="mock-key", fallback_provider=mock_fallback)
        # Simulate Antigravity API returning None (timeout or 429)
        with patch.object(provider, "_call_agent", return_value=None):
            result = provider.generate_fix("test prompt")

        self.assertIsNotNone(result)
        self.assertEqual(result.summary, "Fixed by fallback")
        mock_fallback.generate_fix.assert_called_once_with("test prompt", None)

    def test_handle_remote_issue_pr(self):
        cfg = Config(
            local=False,
            repo="poingstudios/test-repo",
            issue_number="99",
            issue_title="Fix memory leak",
            github_token="fake_token",
        )
        mock_client = MagicMock()
        mock_client.is_pull_request.return_value = False
        mock_client.create_pull_request.return_value = {
            "number": 101,
            "html_url": "https://github.com/poingstudios/test-repo/pull/101",
        }

        service = FixService(cfg, client=mock_client)
        service.root_dir = self.root_path

        fixes = [
            FileFix(
                file_path="leak.py",
                explanation="Freed pointer",
                original_snippet="alloc()",
                replacement_snippet="alloc(); free()",
            )
        ]
        result = FixResult(
            summary="Resolved memory leak",
            fixes=fixes,
            tests_passed=True,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            service._handle_remote_commit(result, fixes)

        mock_client.create_pull_request.assert_called_once()
        _, kwargs = mock_client.create_pull_request.call_args
        self.assertEqual(kwargs["repo"], "poingstudios/test-repo")
        self.assertIn("fix(#99): Fix memory leak", kwargs["title"])
        self.assertIn("fix/issue-99-fix-memory-leak", kwargs["head"])

        mock_client.add_comment.assert_called_once()
        c_args, _ = mock_client.add_comment.call_args
        self.assertIn("101", c_args[2])

if __name__ == "__main__":
    unittest.main()
