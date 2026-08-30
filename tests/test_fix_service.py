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


if __name__ == "__main__":
    unittest.main()
