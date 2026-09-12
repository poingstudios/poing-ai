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

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from poing_ai.ai.thread_resolver import (
    collect_thread_fingerprints,
    fetch_resolved_thread_locations,
    resolve_fixed_threads,
)
from poing_ai.core.config import fingerprint


class TestThreadResolver(unittest.TestCase):
    def test_fetch_resolved_thread_locations(self):
        threads = [
            {
                "id": "thread-1",
                "isResolved": True,
                "isOutdated": False,
                "path": "src/main.gd",
                "line": 15,
            },
            {
                "id": "thread-2",
                "isResolved": True,
                "isOutdated": True,  # Code was changed, so should not suppress
                "path": "src/main.gd",
                "line": 30,
            },
            {
                "id": "thread-3",
                "isResolved": False,
                "isOutdated": False,
                "path": "src/other.gd",
                "line": 42,
            },
            {
                "id": "thread-4",
                "isResolved": True,
                "isOutdated": False,
                "path": "src/file_no_line.gd",
                "line": None,
            },
        ]

        resolved_locs = fetch_resolved_thread_locations(threads)
        self.assertEqual(resolved_locs, {("src/main.gd", 15)})

    def test_resolve_fixed_threads_prevents_false_resolution_on_active_location(self):
        old_comment = "Variable x is never initialized"
        fp_old = fingerprint("src/main.gd", old_comment, 15)

        mock_client = MagicMock()
        mock_client.fetch_review_threads.return_value = [
            {
                "id": "thread-1",
                "isResolved": False,
                "path": "src/main.gd",
                "line": 15,
                "comments": {
                    "nodes": [
                        {
                            "databaseId": 1001,
                            "author": {"login": "poing-ai[bot]"},
                            "body": old_comment,
                        }
                    ]
                },
            }
        ]

        # In current review, the LLM reworded the comment on line 15:
        new_comment = "x is uninitialized and can trigger NPE"
        fp_new = fingerprint("src/main.gd", new_comment, 15)

        # When current_locations contains ("src/main.gd", 15), it should NOT resolve thread
        resolved_count = resolve_fixed_threads(
            client=mock_client,
            owner="poingstudios",
            repo_name="test-repo",
            pr_number="123",
            current_fingerprints={fp_new},
            reviewed_paths={"src/main.gd"},
            bot_login="poing-ai[bot]",
            current_locations={("src/main.gd", 15)},
        )

        self.assertEqual(resolved_count, 0)
        mock_client.resolve_thread.assert_not_called()

    def test_resolve_fixed_threads_resolves_when_issue_fixed(self):
        old_comment = "Variable x is never initialized"
        fp_old = fingerprint("src/main.gd", old_comment, 15)

        mock_client = MagicMock()
        mock_client.fetch_review_threads.return_value = [
            {
                "id": "thread-1",
                "isResolved": False,
                "path": "src/main.gd",
                "line": 15,
                "comments": {
                    "nodes": [
                        {
                            "databaseId": 1001,
                            "author": {"login": "poing-ai[bot]"},
                            "body": old_comment,
                        }
                    ]
                },
            }
        ]
        mock_client.resolve_thread.return_value = True

        # Current review has no comments on line 15
        resolved_count = resolve_fixed_threads(
            client=mock_client,
            owner="poingstudios",
            repo_name="test-repo",
            pr_number="123",
            current_fingerprints=set(),
            reviewed_paths={"src/main.gd"},
            bot_login="poing-ai[bot]",
            current_locations=set(),
        )

        self.assertEqual(resolved_count, 1)
        mock_client.resolve_thread.assert_called_once_with("thread-1")


if __name__ == "__main__":
    unittest.main()
