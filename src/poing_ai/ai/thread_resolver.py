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

from typing import Any, Dict, List, Optional, Set, Tuple

from poing_ai.ai.false_positive import strip_footer
from poing_ai.core.config import fingerprint
from poing_ai.core.github_client import GitHubClient
from poing_ai.core.logging import get_logger

logger = get_logger("ai.thread_resolver")


def collect_thread_fingerprints(
    threads: List[Dict[str, Any]],
    bot_login: Optional[str] = None,
) -> Tuple[Set[str], Dict[str, Dict[str, Any]]]:
    unresolved_fp: Set[str] = set()
    fp_to_thread: Dict[str, Dict[str, Any]] = {}

    for thread in threads:
        if not thread:
            continue
        comments = (thread.get("comments") or {}).get("nodes") or []
        if not comments:
            continue

        first = comments[0]
        if not first:
            continue
        author_login = (first.get("author") or {}).get("login", "")
        raw_body = first.get("body", "")

        is_bot = (
            (bot_login and author_login.lower() == bot_login.lower())
            or "bot" in author_login.lower()
            or "poing-ai" in author_login.lower()
            or "👍 helpful · 👎 false positive" in raw_body
            or "About Poing AI" in raw_body
        )
        if not is_bot:
            continue

        body = strip_footer(first.get("body", ""))
        path = thread.get("path", "")
        line = thread.get("line")
        fp = fingerprint(path, body, line)

        if not thread.get("isResolved", False):
            unresolved_fp.add(fp)

        fp_to_thread[fp] = {
            "id": thread.get("id"),
            "comment_id": first.get("databaseId"),
            "path": path,
            "line": line,
            "body": body,
            "is_resolved": thread.get("isResolved", False),
        }

    return unresolved_fp, fp_to_thread


def resolve_fixed_threads(
    client: GitHubClient,
    owner: str,
    repo_name: str,
    pr_number: str,
    current_fingerprints: Set[str],
    reviewed_paths: Set[str],
    bot_login: Optional[str] = None,
) -> int:
    threads = client.fetch_review_threads(owner, repo_name, pr_number)
    if not threads:
        return 0

    _, fp_to_thread = collect_thread_fingerprints(threads, bot_login)

    resolved_count = 0
    repo = f"{owner}/{repo_name}"
    for fp, info in fp_to_thread.items():
        if info["is_resolved"]:
            continue
        if info["path"] not in reviewed_paths:
            continue
        if fp not in current_fingerprints:
            thread_id = info["id"]
            comment_id = info["comment_id"]

            resolved = client.resolve_thread(thread_id)
            if resolved:
                logger.info(f"Resolved thread for {info['path']} L{info['line']} (finding fixed)")
                resolved_count += 1
            else:
                if comment_id:
                    client.post_thread_comment(
                        repo,
                        comment_id,
                        "✅ This issue appears to be resolved in the latest push.",
                    )
                    logger.info(f"Posted 'resolved' reply for thread {thread_id}")
                    resolved_count += 1

    return resolved_count
