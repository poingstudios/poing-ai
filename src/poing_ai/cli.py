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
import warnings
from typing import List, Optional

# Suppress harmless urllib3 LibreSSL warning on macOS default Python builds
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")

try:
    from poing_ai import __version__
except Exception:
    __version__ = "1.0.1"

from poing_ai.core.config import Config
from poing_ai.core.logging import get_logger
from poing_ai.services.review_service import ReviewService
from poing_ai.services.sync_service import SyncService
from poing_ai.services.triage_service import TriageService

logger = get_logger("cli")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="poing",
        description="Poing AI: AI Code Review, Triage, and Multi-Platform Dependency Automation.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"poing-ai {__version__}",
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
        "-p",
        "--provider",
        choices=["auto", "gemini", "ollama", "openai", "openai-compatible", "deepseek", "groq", "openrouter"],
        default=None,
        help="AI provider backend (gemini, ollama, openai, deepseek, or auto)",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=None,
        help="Primary AI model name (e.g. gemini-3.7-flash, deepseek-r1:latest, gpt-4o-mini)",
    )
    parser.add_argument(
        "--api-base",
        "--base-url",
        dest="api_base",
        default=None,
        help="Custom API base URL (e.g. http://localhost:11434 for Ollama, https://api.deepseek.com/v1)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API Key for remote AI providers (Gemini, OpenAI, DeepSeek)",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Review only staged git changes (git diff --cached)",
    )
    parser.add_argument(
        "--diff-target",
        default=None,
        help="Custom git diff range/commit to review (e.g. HEAD~1, master...HEAD)",
    )
    parser.add_argument(
        "-f",
        "--files",
        nargs="+",
        default=None,
        help="Review specific file path(s)",
    )
    parser.add_argument(
        "-o",
        "--output",
        choices=["terminal", "json", "markdown"],
        default=None,
        help="Local review output format (default: terminal)",
    )
    parser.add_argument(
        "--fail-on-changes",
        action="store_true",
        help="Exit with code 1 if review verdict is CHANGES_REQUESTED (useful for pre-commit hooks)",
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
        provider=args.provider,
        api_base=args.api_base,
        api_key=args.api_key,
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
        staged=args.staged,
        diff_target=args.diff_target,
        files=args.files,
        output_format=args.output,
        fail_on_changes=args.fail_on_changes,
    )

    mode = cfg.MODE
    logger.info(f"Running Poing AI in '{mode}' mode (local={cfg.LOCAL}, provider={cfg.PROVIDER}, dry_run={cfg.DRY_RUN})...")

    try:
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
        if review_result is None:
            return 1

        if cfg.LOCAL and cfg.FAIL_ON_CHANGES and review_result.verdict.value == "CHANGES_REQUESTED":
            return 1

        return 0
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
