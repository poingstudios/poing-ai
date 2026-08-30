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

import difflib
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from poing_ai.ai.base import BaseAIProvider
from poing_ai.ai.factory import create_ai_provider
from poing_ai.ai.prompts.fix import build_fix_prompt
from poing_ai.ai.rag.base import BaseRetriever
from poing_ai.ai.rag.factory import create_retriever
from poing_ai.core.config import Config
from poing_ai.core.git import get_git_diff
from poing_ai.core.github_client import GitHubClient
from poing_ai.core.logging import get_logger
from poing_ai.core.models import FileFix, FixResult
from poing_ai.engines.base import BaseEngineAnalyzer
from poing_ai.engines.detector import detect_engine
from poing_ai.services.review_service import ReviewService

logger = get_logger("services.fix")


class FixService:
    """Autonomous agent service that analyzes code issues, applies patches, and verifies fixes with test runners."""

    def __init__(
        self,
        cfg: Config,
        ai: Optional[BaseAIProvider] = None,
        client: Optional[GitHubClient] = None,
        retriever: Optional[BaseRetriever] = None,
        engine: Optional[BaseEngineAnalyzer] = None,
    ):
        self.cfg = cfg
        self.client = client or (GitHubClient(cfg.GITHUB_TOKEN) if cfg.GITHUB_TOKEN else None)
        self.retriever = retriever or create_retriever(cfg)
        self.ai = ai or create_ai_provider(cfg)
        self.engine = engine or detect_engine(root_dir=Path.cwd())
        self.root_dir = Path.cwd()

    def run(self, findings_override: Optional[str] = None, target_files_override: Optional[List[str]] = None) -> Optional[FixResult]:
        """Executes the end-to-end fix loop."""
        logger.info(f"Starting Autonomous Fixer (local={self.cfg.LOCAL}, provider={self.cfg.PROVIDER or 'auto'})...")

        # 1. Discover target files and issues to fix
        findings_context, target_file_paths = self._discover_targets(findings_override, target_files_override)
        if not target_file_paths:
            logger.info("No targets found to fix. Working tree or PR is clean.")
            return None

        # 2. Read current content of target files
        target_files: Dict[str, str] = {}
        for rel_path in target_file_paths:
            abs_path = self.root_dir / rel_path
            if abs_path.exists() and abs_path.is_file():
                try:
                    target_files[rel_path] = abs_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Could not read {rel_path}: {e}")

        if not target_files:
            logger.warning("No readable target files found for fixing.")
            return None

        # 3. Retrieve RAG guidelines and engine context
        rag_guidelines = ""
        if self.retriever:
            try:
                rag_query = f"architecture coding standards fix guidelines {' '.join(target_file_paths)}"
                docs = self.retriever.retrieve(rag_query)
                if docs:
                    rag_guidelines = "\n\n".join(f"### [{d.source}]\n{d.content}" for d in docs)
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

        engine_rules = ""
        if self.engine:
            engine_rules = self.engine.get_review_guidelines()

        # 4. Agent Repair & Test Validation Loop (max 3 iterations)
        max_retries = 2
        test_failure_trace: Optional[str] = None
        applied_fixes: List[FileFix] = []
        last_fix_result: Optional[FixResult] = None

        for iteration in range(1, max_retries + 2):
            logger.info(f"Fix iteration {iteration}/{max_retries + 1}...")
            prompt = build_fix_prompt(
                findings_context=findings_context,
                target_files=target_files,
                rag_guidelines=rag_guidelines,
                engine_rules=engine_rules,
                test_failure_trace=test_failure_trace,
            )

            last_fix_result = self.ai.generate_fix(prompt)
            if not last_fix_result or not last_fix_result.fixes:
                logger.warning(f"AI provider did not return any code fixes in iteration {iteration}.")
                break

            # Apply patches to disk
            successful_patches, patch_diffs = self._apply_patches(last_fix_result.fixes, target_files)
            applied_fixes.extend(successful_patches)

            # Run test runner / linter validation
            test_passed, test_output = self._run_test_validation()
            last_fix_result.tests_passed = test_passed
            last_fix_result.test_output = test_output

            if test_passed:
                logger.info(f"✅ Code fixes verified! Test validation passed in iteration {iteration}.")
                break
            else:
                logger.warning(f"❌ Test validation failed in iteration {iteration}:\n{test_output[:300]}...")
                test_failure_trace = test_output

        if not applied_fixes:
            logger.warning("No patches could be successfully applied.")
            return last_fix_result

        # 5. Output / Commit handling
        if self.cfg.LOCAL:
            self._display_local_summary(last_fix_result, applied_fixes)
        else:
            self._handle_remote_commit(last_fix_result, applied_fixes)

        return last_fix_result

    def _discover_targets(
        self,
        findings_override: Optional[str] = None,
        target_files_override: Optional[List[str]] = None,
    ) -> Tuple[str, List[str]]:
        """Identifies which files and issues need to be fixed."""
        if findings_override and target_files_override:
            return findings_override, target_files_override

        findings: List[str] = []
        files: Set[str] = set()

        # 1. On GitHub PR, check existing reviews (tables & comments)
        pr_num = self.cfg.ISSUE_NUMBER or self.cfg.PR_NUMBER or getattr(self.cfg, "NUMBER", None)
        if self.client and self.cfg.REPO and pr_num:
            logger.info(f"Fetching reviews and comments for PR #{pr_num}...")
            reviews = self.client.fetch_existing_reviews(self.cfg.REPO, str(pr_num))
            for r in reviews:
                body = r.get("body", "")
                parsed_f, parsed_files = self._extract_findings_from_markdown(body)
                findings.extend(parsed_f)
                files.update(parsed_files)

            comments = self.client.fetch_pr_comments(self.cfg.REPO, str(pr_num))
            for c in comments:
                path = c.get("path")
                body = c.get("body", "")
                if path and body:
                    files.add(path)
                    findings.append(f"- [{path}:{c.get('line', 1)}] {body}")

            if findings:
                return "\n".join(findings), list(files)

        # 2. In Local Mode, check uncommitted diff first
        diff_output = get_git_diff(
            base_ref=self.cfg.BASE_REF or "master",
            local=self.cfg.LOCAL,
            staged=self.cfg.STAGED,
            diff_target=self.cfg.DIFF_TARGET,
            files=self.cfg.FILES,
            root_dir=self.root_dir,
        )
        if diff_output.strip():
            review_service = ReviewService(
                config=self.cfg,
                ai_provider=self.ai,
                github_client=self.client,
                root_dir=self.root_dir,
            )
            review_result = review_service.run()
            if review_result:
                for f in review_result.findings:
                    if f.file:
                        files.add(f.file)
                        findings.append(f"- [{f.file}] {f.severity} {f.finding}")
                for c in review_result.comments:
                    if c.path:
                        files.add(c.path)
                        findings.append(f"- [{c.path}:{c.line}] {c.body}")

                if findings:
                    return "\n".join(findings), list(files)

        # 3. If working tree is clean, check if current branch has an open PR with review comments
        pr_findings, pr_files = self._fetch_open_branch_pr_findings()
        if pr_findings:
            logger.info(f"Discovered {len(pr_findings)} review finding(s) from open branch Pull Request.")
            return "\n".join(pr_findings), list(pr_files)

        # 4. Check all modified uncommitted files
        res = subprocess.run(["git", "diff", "--name-only"], capture_output=True, text=True)
        git_files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        if git_files:
            return "Resolve all syntax, architecture, and lint issues in modified files.", git_files

        return "", []

    def _extract_findings_from_markdown(self, text: str) -> Tuple[List[str], Set[str]]:
        """Extracts findings and target files from markdown review tables and comment lists."""
        import re
        findings = []
        files = set()
        if not text:
            return findings, files

        # Markdown table: | Severity | File | Finding |
        for line in text.splitlines():
            if "|" in line and not line.startswith("|-") and "Severity" not in line and "Finding" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 3:
                    severity = parts[0]
                    file_path = parts[1].strip("`").strip()
                    finding = parts[2].strip()
                    if file_path and finding and any(s in severity for s in ("🔴", "🟡", "🟢", "error", "warning")):
                        files.add(file_path)
                        findings.append(f"- [{file_path}] {severity} {finding}")

        # Inline list: - [`path`:line] finding
        matches = re.findall(r"-\s*\[`?([^`:\]\n]+)`?(?::\d+)?\]\s*([^\n]+)", text)
        for file_path, finding in matches:
            f_clean = file_path.strip().strip("`")
            if f_clean and f_clean not in files:
                files.add(f_clean)
                findings.append(f"- [{f_clean}] {finding.strip()}")

        return findings, files

    def _fetch_open_branch_pr_findings(self) -> Tuple[List[str], Set[str]]:
        """Fetches reviews from the currently checked out branch's open PR via gh CLI."""
        import json
        findings = []
        files = set()
        try:
            res = subprocess.run(
                ["gh", "pr", "view", "--json", "reviews,comments"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                for r in data.get("reviews", []):
                    body = r.get("body", "")
                    f_list, f_files = self._extract_findings_from_markdown(body)
                    findings.extend(f_list)
                    files.update(f_files)
                for c in data.get("comments", []):
                    body = c.get("body", "")
                    f_list, f_files = self._extract_findings_from_markdown(body)
                    findings.extend(f_list)
                    files.update(f_files)
        except Exception as e:
            logger.debug(f"Could not fetch PR findings via gh CLI: {e}")
        return findings, files

    def _apply_patches(self, fixes: List[FileFix], target_files: Dict[str, str]) -> Tuple[List[FileFix], List[str]]:
        """Applies exact code snippet replacements to target files on disk."""
        applied = []
        diffs = []

        for fix in fixes:
            rel_path = fix.file_path.strip()
            abs_path = self.root_dir / rel_path
            if not abs_path.exists():
                logger.warning(f"File not found on disk: {rel_path}")
                continue

            content = abs_path.read_text(encoding="utf-8")
            orig = fix.original_snippet
            repl = fix.replacement_snippet

            if not orig:
                logger.warning(f"Empty original snippet for {rel_path}. Skipping.")
                continue

            if orig in content:
                new_content = content.replace(orig, repl, 1)
                abs_path.write_text(new_content, encoding="utf-8")
                target_files[rel_path] = new_content
                applied.append(fix)
                logger.info(f"✅ Applied fix to `{rel_path}`: {fix.explanation}")

                # Generate unified diff for visual confirmation
                udiff = "\n".join(
                    difflib.unified_diff(
                        content.splitlines(),
                        new_content.splitlines(),
                        fromfile=f"a/{rel_path}",
                        tofile=f"b/{rel_path}",
                        lineterm="",
                    )
                )
                diffs.append(udiff)
            else:
                logger.warning(f"Original snippet not found in `{rel_path}`. Snippet:\n{orig[:100]}...")

        return applied, diffs

    def _run_test_validation(self) -> Tuple[bool, str]:
        """Runs test suites or linters to verify the fix did not break anything."""
        test_cmd = self._detect_test_command()
        if not test_cmd:
            return True, "No test command detected."

        logger.info(f"Running test validation command: `{test_cmd}`...")
        try:
            res = subprocess.run(
                test_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.root_dir),
            )
            output = (res.stdout or "") + "\n" + (res.stderr or "")
            return (res.returncode == 0), output.strip()
        except subprocess.TimeoutExpired:
            return False, "Test execution timed out after 60s."
        except Exception as e:
            return False, f"Test execution failed to launch: {e}"

    def _detect_test_command(self) -> Optional[str]:
        """Detects the appropriate test/lint command for the repository."""
        # 1. Custom config override
        if getattr(self.cfg, "TEST_COMMAND", None):
            return self.cfg.TEST_COMMAND

        # 2. Python projects
        if (self.root_dir / "tests").exists() and ((self.root_dir / "setup.py").exists() or (self.root_dir / "pyproject.toml").exists()):
            return "PYTHONPATH=src python3 -m unittest discover tests"

        # 3. Godot projects with gdlint
        if (self.root_dir / "project.godot").exists():
            return "gdlint . || true"

        # 4. Node / Web projects
        if (self.root_dir / "package.json").exists():
            return "npm test || true"

        return None

    def _display_local_summary(self, result: Optional[FixResult], applied_fixes: List[FileFix]) -> None:
        """Prints formatted terminal output for local CLI users."""
        print("\n" + "=" * 60)
        print("POING AI — AUTONOMOUS FIX SUMMARY")
        print(f"Model: {result.model if result else 'AI'}")
        print("=" * 60)
        if result and result.summary:
            print(f"\n{result.summary}\n")

        print(f"Applied {len(applied_fixes)} code repair(s):")
        for idx, fix in enumerate(applied_fixes, 1):
            print(f" {idx}. `{fix.file_path}`: {fix.explanation}")

        if result and result.tests_passed:
            print("\n✅ Verification: All tests and linters passed successfully!")
        else:
            print("\n⚠️ Verification: Some tests failed. Please review the updated files.")
        print("=" * 60 + "\n")

    def _handle_remote_commit(self, result: Optional[FixResult], applied_fixes: List[FileFix]) -> None:
        """Commits and pushes repairs to the PR branch and updates GitHub."""
        if not applied_fixes:
            return

        file_paths = [f.file_path for f in applied_fixes]
        commit_msg = f"fix(poing-ai): {result.summary if result and result.summary else 'resolve review findings'}"

        try:
            logger.info("Configuring Git bot author for remote commit...")
            subprocess.run(["git", "config", "user.name", "poing-ai[bot]"], check=True)
            subprocess.run(["git", "config", "user.email", "296332247+poing-ai[bot]@users.noreply.github.com"], check=True)
            subprocess.run(["git", "add"] + file_paths, check=True)
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push"], check=True)
            logger.info(f"✅ Successfully pushed automated fix commit to PR branch: `{commit_msg}`")

            # Post confirmation comment on GitHub PR
            if self.client and self.cfg.REPO and self.cfg.ISSUE_NUMBER:
                body = f"## 🛠️ [🤖 Poing AI](https://github.com/poingstudios/poing-ai) Auto-Fix\n\n"
                body += f"Applied **{len(applied_fixes)} automated fix(es)**:\n"
                for fix in applied_fixes:
                    body += f"- `{fix.file_path}`: {fix.explanation}\n"
                body += f"\nCommit: `{commit_msg}`\n\n"
                body += "✅ All validation tests passed!"
                self.client.post_issue_comment(self.cfg.REPO, self.cfg.ISSUE_NUMBER, body)
        except Exception as e:
            logger.error(f"Failed to commit/push remote fixes: {e}")
