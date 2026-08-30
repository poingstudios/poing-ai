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

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from poing_ai.ai.base import BaseAIProvider
from poing_ai.ai.factory import create_ai_provider
from poing_ai.ai.prompts.triage import build_triage_prompt
from poing_ai.core.config import (
    AVAILABLE_LABELS,
    PRIORITY_LABELS,
    TRIAGE_FOOTER,
    Config,
)
from poing_ai.core.github_client import GitHubClient
from poing_ai.core.logging import get_logger
from poing_ai.core.models import TriagePriority, TriageResult

logger = get_logger("services.triage")

DEFAULT_LABEL_COLORS = {
    "bug": ("d73a4a", "Something isn't working"),
    "enhancement": ("a2eeef", "New feature or request"),
    "documentation": ("0075ca", "Improvements or additions to documentation"),
    "question": ("d876e3", "Further information is requested"),
    "help wanted": ("008672", "Extra attention is needed"),
    "ios": ("C5DEF5", "iOS platform"),
    "android": ("1FD539", "Android platform"),
    "wontfix": ("ffffff", "This will not be worked on"),
    "dependencies": ("0366d6", "Automated dependency updates"),
    "high priority": ("b60205", "High priority issue"),
    "medium priority": ("fbca04", "Medium priority issue"),
    "low priority": ("0e8a16", "Low priority issue"),
    "duplicate": ("cfd3d7", "This issue or pull request already exists"),
}


def _normalize_label(label: str) -> str:
    return label.lower().strip()


class TriageService:
    def __init__(
        self,
        config: Config,
        ai_provider: Optional[BaseAIProvider] = None,
        github_client: Optional[GitHubClient] = None,
        root_dir: Optional[Path] = None,
    ):
        self.cfg = config
        self.root_dir = root_dir or Path.cwd()
        self.ai = ai_provider or create_ai_provider(config)
        self.client = github_client or GitHubClient(token=config.GITHUB_TOKEN)

    def _ensure_labels_exist(self, labels_to_ensure: List[str], existing_labels: List[Dict[str, Any]]) -> None:
        existing_names = [_normalize_label(l["name"]) for l in existing_labels]
        for label in labels_to_ensure:
            norm = _normalize_label(label)
            if norm not in existing_names:
                color, desc = DEFAULT_LABEL_COLORS.get(norm, ("ededed", "Auto-generated label"))
                if not self.cfg.DRY_RUN:
                    self.client.create_label(self.cfg.REPO, norm, color=color, description=desc)
                logger.info(f"Created missing label: {norm}")

    def run(self) -> Optional[TriageResult]:
        logger.info(f"Triaging issue/PR #{self.cfg.ISSUE_NUMBER} ({self.cfg.ISSUE_ACTION})...")

        if not self.cfg.LOCAL:
            if self.cfg.ISSUE_ACTION in ("edited", "reopened"):
                logger.info(f"Skipping automatic triage for action '{self.cfg.ISSUE_ACTION}'.")
                return None

            if self.cfg.ISSUE_ACTION == "comment" and self.cfg.COMMENT_BODY:
                if not self.cfg.IS_MAINTAINER:
                    logger.info("Comment not from maintainer. Skipping triage.")
                    return None
                if "/triage" not in self.cfg.COMMENT_BODY.lower():
                    logger.info("Comment does not contain /triage. Skipping.")
                    return None
                logger.info("Manual triage triggered by maintainer via /triage.")

        title = self.cfg.ISSUE_TITLE
        body = self.cfg.ISSUE_BODY or ""

        if not self.cfg.LOCAL and self.cfg.REPO and self.cfg.ISSUE_NUMBER:
            issue_data = self.client.fetch_issue(self.cfg.REPO, self.cfg.ISSUE_NUMBER)
            if issue_data:
                title = issue_data.get("title", title)
                body = issue_data.get("body", body) or ""

        if not body.strip():
            body = f"(No description provided. Title: {title})"

        prompt = build_triage_prompt(title, body, AVAILABLE_LABELS)
        result = self.ai.generate_triage(prompt)

        if not result:
            logger.error("AI triage generation failed.")
            return None

        logger.info(f"Triage result: labels={result.labels}, priority={result.priority.value}, summary={result.summary}")

        labels_to_add = [l for l in result.labels if _normalize_label(l) in [_normalize_label(a) for a in AVAILABLE_LABELS]]
        priority_label = PRIORITY_LABELS.get(result.priority.value)
        if priority_label:
            labels_to_add.append(priority_label)

        if self.cfg.LOCAL:
            print("\n" + "=" * 60)
            print(f"TRIAGE RESULT for '{title}'")
            print(f"Priority: {result.priority.value.upper()}")
            print(f"Labels: {', '.join(labels_to_add)}")
            print(f"Summary: {result.summary}")
            print(f"Duplicate?: {'Yes' if result.is_duplicate else 'No'}")
            print("=" * 60 + "\n")
            return result

        if not self.cfg.REPO or not self.cfg.ISSUE_NUMBER:
            return result

        existing_labels = self.client.fetch_issue_labels(self.cfg.REPO)
        self._ensure_labels_exist(labels_to_add, existing_labels)

        # Remove outdated priority labels
        issue_data = self.client.fetch_issue(self.cfg.REPO, self.cfg.ISSUE_NUMBER)
        current_labels = [l["name"] for l in issue_data.get("labels", [])] if issue_data else []
        labels_to_remove = [
            l for l in current_labels
            if l in PRIORITY_LABELS.values() and l not in labels_to_add
        ]

        if not self.cfg.DRY_RUN:
            for l in labels_to_remove:
                self.client.remove_label_from_issue(self.cfg.REPO, self.cfg.ISSUE_NUMBER, l)
            new_labels = [l for l in labels_to_add if l not in current_labels]
            if new_labels:
                self.client.add_labels_to_issue(self.cfg.REPO, self.cfg.ISSUE_NUMBER, new_labels)

        logger.info(f"Issue #{self.cfg.ISSUE_NUMBER} triaged successfully.")
        return result
