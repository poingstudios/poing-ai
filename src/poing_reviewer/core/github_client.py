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

import json
import re
import sys
from typing import Any, Dict, List, Optional
import requests

from poing_reviewer.core.logging import get_logger

logger = get_logger("github_client")

BASE_URL = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"


class GitHubClient:
    def __init__(self, token: str):
        self.token = token

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _graphql_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "PoingReviewer/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def fetch_bot_login(self) -> str:
        if not self.token:
            return ""
        resp = requests.get(f"{BASE_URL}/user", headers=self._headers())
        if resp.status_code == 200:
            return resp.json().get("login", "")
        return ""

    def fetch_existing_reviews(self, repo: str, pr_number: str) -> List[Dict[str, Any]]:
        if not self.token or not repo or not pr_number:
            return []
        resp = requests.get(
            f"{BASE_URL}/repos/{repo}/pulls/{pr_number}/reviews",
            headers=self._headers(),
        )
        if resp.status_code == 200:
            return resp.json()
        return []

    def dismiss_review(self, repo: str, pr_number: str, review_id: int, message: str) -> bool:
        resp = requests.put(
            f"{BASE_URL}/repos/{repo}/pulls/{pr_number}/reviews/{review_id}/dismissals",
            headers=self._headers(),
            json={"message": message},
        )
        return resp.status_code == 200

    def submit_review(
        self,
        repo: str,
        pr_number: str,
        body: str,
        event: str,
        comments: Optional[List[Dict[str, Any]]] = None,
    ) -> requests.Response:
        payload: Dict[str, Any] = {"body": body.strip(), "event": event}
        if comments:
            payload["comments"] = comments
        resp = requests.post(
            f"{BASE_URL}/repos/{repo}/pulls/{pr_number}/reviews",
            headers=self._headers(),
            json=payload,
        )
        return resp

    def submit_review_with_retry(
        self,
        repo: str,
        pr_number: str,
        body: str,
        event: str,
        comments: Optional[List[Dict[str, Any]]] = None,
    ) -> requests.Response:
        resp = self.submit_review(repo, pr_number, body, event, comments)
        if resp.status_code == 422:
            error_text = resp.text.lower()
            if "own pull request" in error_text and event != "COMMENT":
                logger.warning("GitHub rejected review event on own pull request. Retrying as COMMENT...")
                event = "COMMENT"
                resp = self.submit_review(repo, pr_number, body, event, comments)

            if resp.status_code == 422 and comments:
                logger.warning("GitHub rejected 422 with comments. Retrying without inline comments...")
                resp = self.submit_review(repo, pr_number, body, event, comments=None)

                if resp.status_code == 422 and "own pull request" in resp.text.lower() and event != "COMMENT":
                    logger.warning("Retrying as COMMENT without inline comments...")
                    resp = self.submit_review(repo, pr_number, body, "COMMENT", comments=None)

        if resp.status_code >= 400:
            logger.error(f"GitHub API error: {resp.status_code} {resp.text}")
            sys.exit(1)
        logger.info("Review posted successfully!")
        return resp

    def fetch_review_threads(self, owner: str, repo_name: str, pr_number: str) -> List[Dict[str, Any]]:
        if not self.token:
            return []
        query = """
        query($owner: String!, $repo: String!, $pr: Int!) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $pr) {
              reviewThreads(first: 100) {
                nodes {
                  id
                  isResolved
                  path
                  line
                  comments(first: 50) {
                    nodes {
                      author { login }
                      body
                      databaseId
                      pullRequestReview { databaseId }
                      reactions(first: 10) {
                        nodes { content }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        payload = {
            "query": query,
            "variables": {
                "owner": owner,
                "repo": repo_name,
                "pr": int(pr_number),
            },
        }
        try:
            resp = requests.post(GRAPHQL_URL, headers=self._graphql_headers(), json=payload, timeout=30)
            if resp.status_code != 200:
                logger.error(f"GraphQL error (fetch_review_threads): {resp.status_code} {resp.text}")
                return []
            data = resp.json()
            if "errors" in data:
                logger.error(f"GraphQL errors: {json.dumps(data['errors'])}")
                return []
            return (
                data.get("data", {})
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads", {})
                .get("nodes", [])
            )
        except Exception as e:
            logger.error(f"Failed to fetch review threads: {e}")
            return []

    def resolve_thread(self, thread_id: str) -> bool:
        mutation = """
        mutation($threadId: ID!) {
          resolveReviewThread(input: { threadId: $threadId }) {
            thread { id }
          }
        }
        """
        payload = {"query": mutation, "variables": {"threadId": thread_id}}
        try:
            resp = requests.post(GRAPHQL_URL, headers=self._graphql_headers(), json=payload, timeout=30)
            if resp.status_code != 200:
                return False
            data = resp.json()
            return "errors" not in data
        except Exception:
            return False

    def post_thread_comment(self, repo: str, comment_id: int, body: str) -> bool:
        resp = requests.post(
            f"{BASE_URL}/repos/{repo}/pulls/comments/{comment_id}/replies",
            headers=self._headers(),
            json={"body": body},
        )
        return resp.status_code == 201

    def fetch_issue(self, repo: str, issue_number: str) -> Optional[Dict[str, Any]]:
        resp = requests.get(
            f"{BASE_URL}/repos/{repo}/issues/{issue_number}",
            headers=self._headers(),
        )
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Error fetching issue {issue_number}: {resp.status_code} {resp.text}")
        return None

    def fetch_issue_labels(self, repo: str) -> List[Dict[str, Any]]:
        resp = requests.get(
            f"{BASE_URL}/repos/{repo}/labels",
            headers=self._headers(),
        )
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Error fetching labels for {repo}: {resp.status_code} {resp.text}")
        return []

    def create_label(
        self,
        repo: str,
        name: str,
        color: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {"name": name}
        if color:
            payload["color"] = color
        if description:
            payload["description"] = description
        resp = requests.post(
            f"{BASE_URL}/repos/{repo}/labels",
            headers=self._headers(),
            json=payload,
        )
        if resp.status_code == 201:
            return resp.json()
        return None

    def add_labels_to_issue(self, repo: str, issue_number: str, labels: List[str]) -> bool:
        resp = requests.post(
            f"{BASE_URL}/repos/{repo}/issues/{issue_number}/labels",
            headers=self._headers(),
            json={"labels": labels},
        )
        return resp.status_code == 200

    def remove_label_from_issue(self, repo: str, issue_number: str, label: str) -> bool:
        import urllib.parse
        encoded_label = urllib.parse.quote(label)
        resp = requests.delete(
            f"{BASE_URL}/repos/{repo}/issues/{issue_number}/labels/{encoded_label}",
            headers=self._headers(),
        )
        return resp.status_code in (200, 204)

    def add_comment(self, repo: str, issue_number: str, body: str) -> bool:
        resp = requests.post(
            f"{BASE_URL}/repos/{repo}/issues/{issue_number}/comments",
            headers=self._headers(),
            json={"body": body},
        )
        return resp.status_code == 201

    def verify_action_exists(self, action_ref: str) -> bool:
        if "@" not in action_ref:
            return False
        action_name, version = action_ref.split("@", 1)
        action_parts = action_name.split("/")
        if len(action_parts) < 2:
            return False

        owner = action_parts[0]
        repo = action_parts[1]

        # 1. Check release by tag
        release_url = f"{BASE_URL}/repos/{owner}/{repo}/releases/tags/{version}"
        try:
            resp = requests.get(release_url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                return True
        except Exception:
            pass

        # 2. Check git ref / tag
        ref_url = f"{BASE_URL}/repos/{owner}/{repo}/git/ref/tags/{version}"
        try:
            resp = requests.get(ref_url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                return True
        except Exception:
            pass

        # 3. Check git ref / head (branches like @master, @main)
        branch_url = f"{BASE_URL}/repos/{owner}/{repo}/git/ref/heads/{version}"
        try:
            resp = requests.get(branch_url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                return True
        except Exception:
            pass

        return False

    def extract_and_verify_actions(self, diff_text: str) -> Dict[str, bool]:
        verified_actions: Dict[str, bool] = {}
        action_pattern = re.compile(r'uses:\s*([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)?@([a-zA-Z0-9_.-]+))')

        matches = action_pattern.findall(diff_text)
        for full_match, _ in matches:
            clean_match = full_match.strip("'\"")
            if clean_match not in verified_actions:
                exists = self.verify_action_exists(clean_match)
                verified_actions[clean_match] = exists
                logger.info(f"Verified GitHub Action [{clean_match}]: {'VALID' if exists else 'INVALID'}")
        return verified_actions
