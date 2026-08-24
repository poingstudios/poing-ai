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

import argparse
import os
import sys
from typing import List, Optional

from poing_reviewer.core.config import Config
from poing_reviewer.core.logging import get_logger
from poing_reviewer.services.review_service import ReviewService
from poing_reviewer.services.sync_service import SyncService
from poing_reviewer.services.triage_service import TriageService

logger = get_logger("cli")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="poing-reviewer",
        description="Poing Reviewer: AI Code Review, Triage, and Multi-Platform Dependency Automation.",
    )
    parser.add_argument(
        "--mode",
        choices=["review", "triage", "sync", "dependencies"],
        default=None,
        help="Operation mode (review, triage, or sync)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run locally without requiring GitHub PR context",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without modifying files or submitting reviews/labels to GitHub",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Primary AI model name (e.g. gemini-3.5-flash)",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="GitHub repository in 'owner/repo' format",
    )
    parser.add_argument(
        "--pr-number",
        default=None,
        help="Pull request number",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="Base git branch for diff (e.g. master)",
    )
    parser.add_argument(
        "--pr-title",
        default=None,
        help="Pull request title",
    )
    parser.add_argument(
        "--head-sha",
        default=None,
        help="Pull request head commit SHA",
    )
    parser.add_argument(
        "--issue-number",
        default=None,
        help="Issue number for triage",
    )
    parser.add_argument(
        "--issue-title",
        default=None,
        help="Issue title for triage",
    )
    parser.add_argument(
        "--issue-body",
        default=None,
        help="Issue body for triage",
    )
    parser.add_argument(
        "--issue-action",
        default=None,
        help="Issue action (opened, comment, etc.)",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    cfg = Config(
        mode=args.mode,
        model_name=args.model,
        repo=args.repo,
        pr_number=args.pr_number,
        base_ref=args.base_ref,
        pr_title=args.pr_title,
        head_sha=args.head_sha,
        issue_number=args.issue_number,
        issue_title=args.issue_title,
        issue_body=args.issue_body,
        issue_action=args.issue_action,
        local=args.local,
        dry_run=args.dry_run,
    )

    mode = cfg.MODE
    logger.info(f"Running Poing Reviewer in '{mode}' mode (local={cfg.LOCAL}, dry_run={cfg.DRY_RUN})...")

    if mode == "triage":
        service = TriageService(cfg)
        result = service.run()
        return 0 if result is not None else 1

    if mode in ("sync", "dependencies"):
        service = SyncService(cfg)
        summary = service.run()
        # Export GitHub Action outputs if running in GH Actions
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a", encoding="utf-8") as f:
                f.write(f"has_updates={'true' if summary.has_updates else 'false'}\n")
                # Delimited multiline outputs
                f.write("summary_table<<EOF\n")
                f.write(summary.summary_table + "\n")
                f.write("EOF\n")
                f.write("pr_body<<EOF\n")
                f.write(summary.changelog_notes + "\n")
                f.write("EOF\n")
        return 0

    # Default: mode == "review"
    service = ReviewService(cfg)
    review_result = service.run()
    return 0 if review_result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
