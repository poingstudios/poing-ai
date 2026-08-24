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
from typing import Dict, List, Optional, Set, Tuple

from poing_reviewer.ai.base import BaseAIProvider
from poing_reviewer.ai.false_positive import (
    add_footer_hint,
    fetch_thumbs_down_fingerprints,
    filter_action_version_false_positives,
    filter_model_false_positives,
    filter_speculative_false_positives,
    is_suppressed,
)
from poing_reviewer.ai.gemini import GeminiProvider
from poing_reviewer.ai.prompts.review import build_review_prompt
from poing_reviewer.ai.rag.local_rag import LocalFileRetriever
from poing_reviewer.ai.thread_resolver import resolve_fixed_threads
from poing_reviewer.core.config import (
    GITHUB_EVENT_MAP,
    VERDICT_MAP,
    VERDICT_PRIORITY,
    Config,
    fingerprint,
)
from poing_reviewer.core.git import (
    annotate_diff,
    get_git_diff,
    load_file_contents_for_diff,
    split_batches,
    split_diff_by_file,
)
from poing_reviewer.core.github_client import GitHubClient
from poing_reviewer.core.logging import get_logger
from poing_reviewer.core.models import (
    ReviewComment,
    ReviewFinding,
    ReviewResult,
    ReviewVerdict,
)
from poing_reviewer.engines.detector import detect_engine

logger = get_logger("services.review")


def pick_verdict(verdicts: List[ReviewVerdict]) -> ReviewVerdict:
    best = ReviewVerdict.APPROVED
    best_score = 0
    for v in verdicts:
        score = VERDICT_PRIORITY.get(v.value if isinstance(v, ReviewVerdict) else str(v), 0)
        if score > best_score:
            best_score = score
            best = v if isinstance(v, ReviewVerdict) else ReviewVerdict(v)
    return best


class ReviewService:
    def __init__(
        self,
        config: Config,
        ai_provider: Optional[BaseAIProvider] = None,
        github_client: Optional[GitHubClient] = None,
        root_dir: Optional[Path] = None,
    ):
        self.cfg = config
        self.root_dir = root_dir or Path.cwd()
        self.ai = ai_provider or GeminiProvider(
            api_key=config.GEMINI_API_KEY,
            models_to_try=config.MODELS_TO_TRY,
        )
        self.client = github_client or GitHubClient(token=config.GITHUB_TOKEN)
        if config.GEMINI_API_KEY:
            from poing_reviewer.ai.rag.gemini_embedder import GeminiEmbedder
            from poing_reviewer.ai.rag.vector_rag import VectorRAGRetriever
            self.retriever = VectorRAGRetriever(
                embedder=GeminiEmbedder(api_key=config.GEMINI_API_KEY),
                root_dir=self.root_dir,
            )
        else:
            self.retriever = LocalFileRetriever(root_dir=self.root_dir)

    def run(self) -> ReviewResult:
        logger.info(f"Starting review (local={self.cfg.LOCAL})...")

        diff = get_git_diff(self.cfg.BASE_REF, local=self.cfg.LOCAL)
        if not diff.strip():
            logger.info("No diff detected. Skipping review.")
            return ReviewResult(
                verdict=ReviewVerdict.APPROVED,
                summary="No changes detected in diff.",
            )

        if not self.cfg.LOCAL and self.cfg.GITHUB_TOKEN and not self.cfg.BOT_LOGIN:
            self.cfg.BOT_LOGIN = self.client.fetch_bot_login()

        # Check existing reviews in PR mode
        if not self.cfg.LOCAL and self.cfg.REPO and self.cfg.PR_NUMBER:
            existing_reviews = self.client.fetch_existing_reviews(self.cfg.REPO, self.cfg.PR_NUMBER)
            is_re_request = (
                self.cfg.TRIGGER_ACTION in ("review_requested", "workflow_dispatch")
                or "/review" in self.cfg.COMMENT_BODY.lower()
            )
            bot_reviews = [
                r for r in existing_reviews
                if r.get("user", {}).get("login") == self.cfg.BOT_LOGIN and r.get("state") != "PENDING"
            ]

            if bot_reviews:
                if is_re_request:
                    logger.info("Re-review requested. Dismissing existing bot reviews.")
                    for review in bot_reviews:
                        self.client.dismiss_review(
                            self.cfg.REPO,
                            self.cfg.PR_NUMBER,
                            review["id"],
                            f"Re-review triggered on commit {self.cfg.HEAD_SHA[:8]}",
                        )
                else:
                    logger.info("PR has already been reviewed by bot. Skipping.")
                    return ReviewResult(
                        verdict=ReviewVerdict.APPROVED,
                        summary="PR already reviewed.",
                    )

        # Context & Guidelines
        guidelines_docs = self.retriever.retrieve(query="guidelines coding standards", top_k=3)
        guidelines_text = ""
        if guidelines_docs:
            guidelines_text = "## Repository Guidelines\n" + "\n\n".join(
                f"### {doc.source}\n{doc.content}" for doc in guidelines_docs
            )

        engine_analyzer = detect_engine(
            root_dir=self.root_dir,
            explicit_engine=self.cfg.file_config.get("engine"),
        )
        engine_guidelines = engine_analyzer.get_review_guidelines()
        logger.info(f"Detected engine/ecosystem: {engine_analyzer.name}")

        # Live Action Verification
        verified_actions: Dict[str, bool] = {}
        if not self.cfg.LOCAL and self.cfg.GITHUB_TOKEN:
            verified_actions = self.client.extract_and_verify_actions(diff)

        # Diff Batching
        file_blocks = split_diff_by_file(diff)
        batches = split_batches(file_blocks, self.cfg.MAX_CHARS)[:self.cfg.MAX_BATCHES]
        total_batches = len(batches)

        all_results: List[ReviewResult] = []
        all_valid_lines: Set[Tuple[str, int]] = set()

        for i, batch in enumerate(batches):
            batch_label = f"You are reviewing part {i + 1} of {total_batches}." if total_batches > 1 else ""
            batch_diff = "".join(batch)
            annotated, valid_lines = annotate_diff(batch_diff)
            all_valid_lines.update(valid_lines)

            batch_file_paths = {p for p, _ in valid_lines}
            file_contents = (
                load_file_contents_for_diff(batch_file_paths, root_dir=self.root_dir)
                if self.cfg.STRICT_GROUND_TRUTH
                else None
            )

            prompt = build_review_prompt(
                pr_title=self.cfg.PR_TITLE or "Local Code Review",
                annotated_diff=annotated,
                guidelines=guidelines_text,
                engine_guidelines=engine_guidelines,
                batch_label=batch_label,
                verified_actions=verified_actions,
                file_contents=file_contents,
            )

            result = self.ai.generate_review(prompt)
            if result:
                all_results.append(result)

        if not all_results:
            logger.error("All model review attempts failed.")
            if not self.cfg.LOCAL:
                sys.exit(1)
            return ReviewResult(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                summary="AI review generation failed.",
            )

        # Aggregate Verdict & Summaries
        verdicts = [r.verdict for r in all_results]
        final_verdict = pick_verdict(verdicts)
        summaries = [r.summary for r in all_results if r.summary]
        final_summary = " ".join(summaries)

        # Deduplicate Findings & Comments
        seen_findings: Set[str] = set()
        unique_findings: List[ReviewFinding] = []
        for r in all_results:
            for f in r.findings:
                fp = fingerprint(f.file, f.finding)
                if fp not in seen_findings:
                    seen_findings.add(fp)
                    unique_findings.append(f)

        seen_comments: Set[str] = set()
        unique_comments: List[ReviewComment] = []
        for r in all_results:
            for c in r.comments:
                if (c.path, c.line) in all_valid_lines:
                    fp = fingerprint(c.path, c.body, c.line)
                    if fp not in seen_comments:
                        seen_comments.add(fp)
                        unique_comments.append(c)

        # Thumbs-down suppression
        if not self.cfg.LOCAL and self.cfg.REPO and self.cfg.PR_NUMBER:
            threads = self.client.fetch_review_threads(self.cfg.owner, self.cfg.repo_name, self.cfg.PR_NUMBER)
            suppressed_fps = fetch_thumbs_down_fingerprints(threads, self.cfg.BOT_LOGIN)
            unique_comments = [
                c for c in unique_comments
                if not is_suppressed(c.body, c.path, c.line, suppressed_fps)
            ]

        # False-positive filters
        unique_findings, unique_comments = filter_action_version_false_positives(
            unique_findings, unique_comments, verified_actions
        )
        unique_findings, unique_comments = filter_speculative_false_positives(
            unique_findings, unique_comments
        )
        unique_findings = filter_model_false_positives(unique_findings)

        final_result = ReviewResult(
            verdict=final_verdict,
            summary=final_summary,
            findings=unique_findings,
            comments=unique_comments,
        )

        if self.cfg.LOCAL:
            self._display_local_review(final_result)
        else:
            self._submit_github_review(final_result)

        return final_result

    def _build_review_body(self, result: ReviewResult) -> str:
        body_parts = [
            f"## Poing Reviewer\n",
            f"### Verdict: {VERDICT_MAP.get(result.verdict.value, str(result.verdict))}\n",
        ]
        if result.summary:
            body_parts.append(f"{result.summary}\n")

        if result.findings:
            body_parts.append("### Findings\n")
            body_parts.append("| Severity | File | Finding |")
            body_parts.append("|---|---|---|")
            for f in result.findings:
                clean_finding = f.finding.replace("\n", " ").replace("|", "\\|")
                body_parts.append(f"| {f.severity} | `{f.file}` | {clean_finding} |")
            body_parts.append("")
        else:
            body_parts.append("✅ No issues found. Clean changes!\n")

        return "\n".join(body_parts)

    def _display_local_review(self, result: ReviewResult) -> None:
        body = self._build_review_body(result)
        print("\n" + "=" * 60)
        print(body)
        if result.comments:
            print("### Inline Comments:")
            for c in result.comments:
                print(f"- `{c.path}` L{c.line}: {c.body}")
        print("=" * 60 + "\n")

    def _submit_github_review(self, result: ReviewResult) -> None:
        if not self.cfg.REPO or not self.cfg.PR_NUMBER:
            logger.error("Cannot submit GitHub review: REPO or PR_NUMBER missing.")
            return

        body = self._build_review_body(result)
        event = GITHUB_EVENT_MAP.get(result.verdict.value, "APPROVE")

        formatted_comments = [
            {
                "path": c.path,
                "line": c.line,
                "body": add_footer_hint(c.body),
            }
            for c in result.comments
        ]

        if not self.cfg.DRY_RUN:
            self.client.submit_review_with_retry(
                repo=self.cfg.REPO,
                pr_number=self.cfg.PR_NUMBER,
                body=body,
                event=event,
                comments=formatted_comments if formatted_comments else None,
            )

            # Auto-resolve fixed threads
            current_fps = {fingerprint(c.path, c.body, c.line) for c in result.comments}
            reviewed_paths = {c.path for c in result.comments} | {f.file for f in result.findings}
            resolve_fixed_threads(
                client=self.client,
                owner=self.cfg.owner,
                repo_name=self.cfg.repo_name,
                pr_number=self.cfg.PR_NUMBER,
                current_fingerprints=current_fps,
                reviewed_paths=reviewed_paths,
                bot_login=self.cfg.BOT_LOGIN,
            )
        else:
            logger.info("[DRY_RUN] Skipped submitting review to GitHub.")
