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
import re
import sys
from typing import Any, Dict, List, Optional
import requests

try:
    import yaml
except ImportError:
    yaml = None

from poing_ai import __version__
from poing_ai.core.action_cache import ActionSchemaCache
from poing_ai.core.logging import get_logger
from poing_ai.core.models import ActionInput, ActionSchema

logger = get_logger("github_client")

BASE_URL = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"


class GitHubClient:
    def __init__(self, token: str, action_cache: Optional[ActionSchemaCache] = None):
        self.token = token
        self.action_cache = action_cache or ActionSchemaCache()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"PoingReviewer/{__version__}",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _graphql_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"PoingReviewer/{__version__}",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def resolve_pr_number(self, owner: str, repo_name: str, identifier: str) -> Optional[str]:
        if not identifier:
            return None
        clean_id = str(identifier).strip().lstrip("#")
        if clean_id.isdigit():
            return clean_id

        if not self.token or not owner or not repo_name:
            return None

        try:
            resp = requests.get(
                f"{BASE_URL}/repos/{owner}/{repo_name}/pulls",
                headers=self._headers(),
                params={"head": f"{owner}:{identifier}", "state": "open"},
                timeout=15,
            )
            if resp.status_code == 200:
                prs = resp.json()
                if prs and isinstance(prs, list) and len(prs) > 0:
                    resolved = str(prs[0].get("number"))
                    logger.info(f"Resolved branch '{identifier}' to PR #{resolved}")
                    return resolved
        except Exception as e:
            logger.debug(f"Failed to resolve PR from branch '{identifier}': {e}")
        return None

    def fetch_bot_login(self) -> str:
        if not self.token:
            return ""
        try:
            resp = requests.get(f"{BASE_URL}/user", headers=self._headers(), timeout=15)
            if resp.status_code == 200:
                return resp.json().get("login", "")
        except Exception as e:
            logger.debug(f"Failed to fetch bot login: {e}")
        return ""

    def fetch_existing_reviews(self, repo: str, pr_number: str) -> List[Dict[str, Any]]:
        if not self.token or not repo or not pr_number:
            return []
        try:
            resp = requests.get(
                f"{BASE_URL}/repos/{repo}/pulls/{pr_number}/reviews",
                headers=self._headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.debug(f"Failed to fetch existing reviews: {e}")
        return []

    def fetch_pr_comments(self, repo: str, pr_number: str) -> List[Dict[str, Any]]:
        if not self.token or not repo or not pr_number:
            return []
        try:
            resp = requests.get(
                f"{BASE_URL}/repos/{repo}/pulls/{pr_number}/comments",
                headers=self._headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.debug(f"Failed to fetch PR comments: {e}")
        return []

    def dismiss_review(self, repo: str, pr_number: str, review_id: int, message: str) -> bool:
        try:
            resp = requests.put(
                f"{BASE_URL}/repos/{repo}/pulls/{pr_number}/reviews/{review_id}/dismissals",
                headers=self._headers(),
                json={"message": message},
                timeout=15,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to dismiss review {review_id}: {e}")
            return False

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
            timeout=30,
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
        current_event = event
        current_comments = comments

        resp = self.submit_review(repo, pr_number, body, current_event, current_comments)

        # Fallback 1: GitHub forbids APPROVE on self-authored PRs -> switch to COMMENT
        if resp.status_code == 422 and "own pull request" in resp.text.lower() and current_event != "COMMENT":
            logger.warning("Cannot approve own pull request. Retrying as COMMENT...")
            current_event = "COMMENT"
            resp = self.submit_review(repo, pr_number, body, current_event, current_comments)

        # Fallback 2: Invalid inline comment line positions -> retry review body only
        if resp.status_code == 422 and current_comments:
            logger.warning("GitHub rejected inline comments (422). Retrying review body only...")
            current_comments = None
            resp = self.submit_review(repo, pr_number, body, current_event, current_comments)

        if resp.status_code >= 400:
            logger.error(f"GitHub API error: {resp.status_code} {resp.text}")
            sys.exit(1)
        logger.info("Review posted successfully!")
        return resp

    def fetch_review_threads(self, owner: str, repo_name: str, pr_number: str) -> List[Dict[str, Any]]:
        if not self.token or not pr_number:
            return []
        try:
            pr_int = int(str(pr_number).strip())
        except (ValueError, TypeError):
            logger.warning(f"Skipping fetch_review_threads: pr_number '{pr_number}' is not a valid integer.")
            return []

        query = """
        query($owner: String!, $repo: String!, $pr: Int!) {
          repository(owner: $owner, name: $repo) {
            pullRequest(number: $pr) {
              reviewThreads(first: 100) {
                nodes {
                  id
                  isResolved
                  isOutdated
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
                "pr": pr_int,
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
        try:
            resp = requests.post(
                f"{BASE_URL}/repos/{repo}/pulls/comments/{comment_id}/replies",
                headers=self._headers(),
                json={"body": body},
                timeout=15,
            )
            return resp.status_code == 201
        except Exception as e:
            logger.warning(f"Failed to post thread comment reply: {e}")
            return False

    def fetch_issue(self, repo: str, issue_number: str) -> Optional[Dict[str, Any]]:
        try:
            resp = requests.get(
                f"{BASE_URL}/repos/{repo}/issues/{issue_number}",
                headers=self._headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"Error fetching issue {issue_number}: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Request failed fetching issue {issue_number}: {e}")
        return None

    def fetch_issue_labels(self, repo: str) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                f"{BASE_URL}/repos/{repo}/labels",
                headers=self._headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"Error fetching labels for {repo}: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Request failed fetching labels for {repo}: {e}")
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
        try:
            resp = requests.post(
                f"{BASE_URL}/repos/{repo}/labels",
                headers=self._headers(),
                json=payload,
                timeout=15,
            )
            if resp.status_code == 201:
                return resp.json()
        except Exception as e:
            logger.warning(f"Failed to create label {name}: {e}")
        return None

    def add_labels_to_issue(self, repo: str, issue_number: str, labels: List[str]) -> bool:
        try:
            resp = requests.post(
                f"{BASE_URL}/repos/{repo}/issues/{issue_number}/labels",
                headers=self._headers(),
                json={"labels": labels},
                timeout=15,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to add labels to issue #{issue_number}: {e}")
            return False

    def remove_label_from_issue(self, repo: str, issue_number: str, label: str) -> bool:
        import urllib.parse
        encoded_label = urllib.parse.quote(label)
        try:
            resp = requests.delete(
                f"{BASE_URL}/repos/{repo}/issues/{issue_number}/labels/{encoded_label}",
                headers=self._headers(),
                timeout=15,
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.warning(f"Failed to remove label {label} from issue #{issue_number}: {e}")
            return False

    def add_comment(self, repo: str, issue_number: str, body: str) -> bool:
        try:
            resp = requests.post(
                f"{BASE_URL}/repos/{repo}/issues/{issue_number}/comments",
                headers=self._headers(),
                json={"body": body},
                timeout=15,
            )
            return resp.status_code == 201
        except Exception as e:
            logger.warning(f"Failed to add comment to issue #{issue_number}: {e}")
            return False

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

    def fetch_action_schema(self, action_ref: str) -> ActionSchema:
        if "@" not in action_ref:
            return ActionSchema(action_ref=action_ref, exists=False)

        # 1. Check cache first
        cached = self.action_cache.get(action_ref)
        if cached is not None:
            return cached

        action_path, version = action_ref.split("@", 1)
        parts = action_path.split("/")
        if len(parts) < 2:
            schema = ActionSchema(action_ref=action_ref, exists=False)
            self.action_cache.set(schema)
            return schema

        owner = parts[0]
        repo = parts[1]
        subpath = "/".join(parts[2:]) if len(parts) > 2 else ""
        path_prefix = f"{subpath}/" if subpath else ""

        manifest_candidates = [
            f"{BASE_URL}/repos/{owner}/{repo}/contents/{path_prefix}action.yml?ref={version}",
            f"{BASE_URL}/repos/{owner}/{repo}/contents/{path_prefix}action.yaml?ref={version}",
        ]

        for url in manifest_candidates:
            try:
                resp = requests.get(url, headers=self._headers(), timeout=10)
                if resp.status_code == 200:
                    raw_text = ""
                    data = resp.json()
                    if isinstance(data, dict) and "content" in data and data.get("encoding") == "base64":
                        raw_text = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                    elif isinstance(data, str):
                        raw_text = data
                    else:
                        raw_text = resp.text

                    inputs: Dict[str, ActionInput] = {}
                    if yaml and raw_text:
                        parsed = yaml.safe_load(raw_text)
                        if isinstance(parsed, dict):
                            raw_inputs = parsed.get("inputs", {})
                            if isinstance(raw_inputs, dict):
                                for iname, idata in raw_inputs.items():
                                    desc = idata.get("description", "") if isinstance(idata, dict) else ""
                                    req = bool(idata.get("required", False)) if isinstance(idata, dict) else False
                                    dep_msg = idata.get("deprecationMessage", "") if isinstance(idata, dict) else ""
                                    is_dep = bool(dep_msg) or "deprecated" in desc.lower()
                                    inputs[str(iname)] = ActionInput(
                                        name=str(iname),
                                        description=desc,
                                        required=req,
                                        deprecated=is_dep,
                                        deprecation_message=dep_msg,
                                    )

                    schema = ActionSchema(action_ref=action_ref, exists=True, inputs=inputs)
                    self.action_cache.set(schema)
                    logger.info(f"Fetched and cached Action schema for [{action_ref}] ({len(inputs)} declared inputs).")
                    return schema
            except Exception as e:
                logger.debug(f"Error fetching action manifest from {url}: {e}")

        # If manifest fetch failed, check if action exists via release/tag/branch
        exists = self.verify_action_exists(action_ref)
        schema = ActionSchema(action_ref=action_ref, exists=exists, inputs={})
        self.action_cache.set(schema)
        return schema

    def extract_and_verify_actions(self, diff_text: str) -> Dict[str, ActionSchema]:
        verified_actions: Dict[str, ActionSchema] = {}
        action_pattern = re.compile(r'uses:\s*([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)?@([a-zA-Z0-9_.-]+))')

        matches = action_pattern.findall(diff_text)
        for full_match, _ in matches:
            clean_match = full_match.strip("'\"")
            if clean_match not in verified_actions:
                schema = self.fetch_action_schema(clean_match)
                verified_actions[clean_match] = schema
                logger.info(f"Verified GitHub Action [{clean_match}]: {'VALID' if schema.exists else 'INVALID'}")

        self.action_cache.save()
        return verified_actions

    def is_pull_request(self, repo: str, number: str) -> bool:
        issue = self.fetch_issue(repo, number)
        return bool(issue and issue.get("pull_request"))

    def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "master",
    ) -> Optional[Dict[str, Any]]:
        try:
            resp = requests.post(
                f"{BASE_URL}/repos/{repo}/pulls",
                headers=self._headers(),
                json={
                    "title": title,
                    "body": body,
                    "head": head,
                    "base": base,
                },
                timeout=20,
            )
            if resp.status_code == 201:
                return resp.json()
            logger.error(f"Failed to create pull request for {head}: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Request failed creating pull request for {head}: {e}")
        return None
