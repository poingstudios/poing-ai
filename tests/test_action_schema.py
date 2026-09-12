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

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from poing_ai.ai.prompts.review import build_review_prompt
from poing_ai.core.action_cache import ActionSchemaCache
from poing_ai.core.github_client import GitHubClient
from poing_ai.core.models import ActionInput, ActionSchema


class TestActionSchema(unittest.TestCase):
    def test_action_input_and_schema_models(self):
        inp1 = ActionInput(
            name="client-id",
            description="The Client ID",
            required=True,
            deprecated=False,
        )
        inp2 = ActionInput(
            name="app-id",
            description="Deprecated parameter",
            required=False,
            deprecated=True,
            deprecation_message="Use client-id instead",
        )
        schema = ActionSchema(
            action_ref="actions/create-github-app-token@v3",
            exists=True,
            inputs={"client-id": inp1, "app-id": inp2},
        )

        self.assertTrue(schema.is_input_declared("client-id"))
        self.assertTrue(schema.is_input_declared("CLIENT-ID"))
        self.assertFalse(schema.is_input_declared("foo-bar"))
        self.assertTrue(schema.is_input_deprecated("app-id"))
        self.assertFalse(schema.is_input_deprecated("client-id"))

        as_dict = schema.to_dict()
        self.assertEqual(as_dict["action_ref"], "actions/create-github-app-token@v3")
        self.assertIn("client-id", as_dict["inputs"])
        self.assertTrue(as_dict["inputs"]["client-id"]["required"])

    def test_action_schema_cache_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / ".poing" / "cache"
            cache = ActionSchemaCache(cache_dir=cache_dir)

            schema = ActionSchema(
                action_ref="actions/checkout@v4",
                exists=True,
                inputs={"fetch-depth": ActionInput(name="fetch-depth", description="Number of commits", required=False)},
            )
            cache.set(schema)
            self.assertIsNotNone(cache.get("actions/checkout@v4"))
            cache.save()

            # Verify saved file
            self.assertTrue((cache_dir / "actions_schema.json").exists())

            # Reload into fresh cache instance
            cache2 = ActionSchemaCache(cache_dir=cache_dir)
            cached_schema = cache2.get("actions/checkout@v4")
            self.assertIsNotNone(cached_schema)
            self.assertTrue(cached_schema.is_input_declared("fetch-depth"))

    def test_fetch_action_schema_live_parsing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ActionSchemaCache(cache_dir=Path(tmp_dir))
            client = GitHubClient(token="mock_token", action_cache=cache)

            mock_action_yaml = """
name: 'Create GitHub App Token'
inputs:
  client-id:
    description: 'The Client ID'
    required: false
  app-id:
    description: 'Deprecated: Use client-id'
    deprecationMessage: 'Use client-id'
  private-key:
    description: 'Private Key'
    required: true
"""
            encoded_content = base64.b64encode(mock_action_yaml.encode("utf-8")).decode("utf-8")

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "content": encoded_content,
                "encoding": "base64",
            }

            with patch("requests.get", return_value=mock_resp):
                schema = client.fetch_action_schema("actions/create-github-app-token@v3")
                self.assertIsNotNone(schema)
                self.assertTrue(schema.exists)
                self.assertTrue(schema.is_input_declared("client-id"))
                self.assertTrue(schema.is_input_declared("app-id"))
                self.assertTrue(schema.is_input_deprecated("app-id"))
                self.assertTrue(schema.inputs["private-key"].required)

                # Ensure it was cached
                self.assertIsNotNone(cache.get("actions/create-github-app-token@v3"))

    def test_extract_and_verify_actions_from_diff(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = ActionSchemaCache(cache_dir=Path(tmp_dir))
            client = GitHubClient(token="mock_token", action_cache=cache)

            diff_text = """
+    - name: 1. Generate App Token
+      uses: actions/create-github-app-token@v3
+      with:
+        client-id: ${{ secrets.APP_ID }}
+    - name: 2. Checkout Code
+      uses: actions/checkout@v4
"""
            mock_resp = MagicMock()
            mock_resp.status_code = 404

            with patch("requests.get", return_value=mock_resp), \
                 patch.object(client, "verify_action_exists", return_value=True):
                verified = client.extract_and_verify_actions(diff_text)
                self.assertEqual(len(verified), 2)
                self.assertIn("actions/create-github-app-token@v3", verified)
                self.assertIn("actions/checkout@v4", verified)
                self.assertTrue(verified["actions/checkout@v4"].exists)

    def test_build_review_prompt_with_action_schemas(self):
        schema = ActionSchema(
            action_ref="actions/create-github-app-token@v3",
            exists=True,
            inputs={
                "client-id": ActionInput(name="client-id"),
                "app-id": ActionInput(name="app-id", deprecated=True),
            },
        )
        prompt = build_review_prompt(
            pr_title="Add action",
            annotated_diff="diff",
            verified_actions={"actions/create-github-app-token@v3": schema},
        )

        self.assertIn("Verified Actions & Ground Truth Schemas", prompt)
        self.assertIn("`actions/create-github-app-token@v3`", prompt)
        self.assertIn("`client-id`", prompt)
        self.assertIn("`app-id` (deprecated)", prompt)
        self.assertIn("Do NOT claim declared inputs are invalid or unsupported", prompt)


if __name__ == "__main__":
    unittest.main()
