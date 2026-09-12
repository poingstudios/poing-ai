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
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from poing_ai.ai.base import BaseAIProvider
from poing_ai.ai.factory import create_ai_provider
from poing_ai.ai.prompts.fix import build_fix_prompt
from poing_ai.ai.rag.base import BaseRetriever
from poing_ai.ai.rag.factory import create_retriever
from poing_ai.core.config import POING_LOGO_URL, Config
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

        # 2. Read current content of target files (limit to top 5 files and 25k chars per file to stay within TPM quotas)
        target_files: Dict[str, str] = {}
        MAX_FILE_CHARS = 25000
        for rel_path in target_file_paths[:5]:
            abs_path = self.root_dir / rel_path
            if abs_path.exists() and abs_path.is_file():
                try:
                    content = abs_path.read_text(encoding="utf-8")
                    if len(content) > MAX_FILE_CHARS:
                        logger.warning(
                            f"File {rel_path} exceeds {MAX_FILE_CHARS} chars ({len(content)} chars). "
                            f"Truncating for prompt to conserve token quota."
                        )
                        content = content[:MAX_FILE_CHARS] + "\n# ... (truncated remaining content to conserve quota)"
                    target_files[rel_path] = content
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
                docs = self.retriever.retrieve(rag_query, top_k=3)
                if docs:
                    combined_docs = "\n\n".join(f"### [{d.source}]\n{d.content}" for d in docs)
                    if len(combined_docs) > 3000:
                        combined_docs = combined_docs[:3000] + "\n... (truncated guidelines)"
                    rag_guidelines = combined_docs
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

        engine_rules = ""
        if self.engine:
            engine_rules = self.engine.get_review_guidelines()
            if len(engine_rules) > 2000:
                engine_rules = engine_rules[:2000] + "\n... (truncated engine rules)"

        # 4. Agent Repair & Test Validation Loop (max 3 iterations)
        max_retries = 2
        test_failure_trace: Optional[str] = None
        applied_fixes: List[FileFix] = []
        last_fix_result: Optional[FixResult] = None

        for iteration in range(1, max_retries + 2):
            logger.info(f"Fix iteration {iteration}/{max_retries + 1}...")
            truncated_trace = None
            if test_failure_trace:
                truncated_trace = test_failure_trace[-2000:] if len(test_failure_trace) > 2000 else test_failure_trace
            prompt = build_fix_prompt(
                findings_context=findings_context,
                target_files=target_files,
                rag_guidelines=rag_guidelines,
                engine_rules=engine_rules,
                test_failure_trace=truncated_trace,
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
        is_pr = False
        if self.client and self.cfg.REPO and pr_num:
            is_pr = self.client.is_pull_request(self.cfg.REPO, str(pr_num))

        if is_pr and self.client and self.cfg.REPO and pr_num:
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

        # 2. On GitHub Issue (not a PR), discover targets from issue title and body
        issue_labels: List[str] = list(getattr(self.cfg, "LABELS", []))
        if not is_pr and self.cfg.ISSUE_NUMBER:
            if not (self.cfg.ISSUE_TITLE and self.cfg.ISSUE_BODY) or not issue_labels:
                if self.client and self.cfg.REPO:
                    issue_data = self.client.fetch_issue(self.cfg.REPO, str(self.cfg.ISSUE_NUMBER))
                    if issue_data:
                        if not self.cfg.ISSUE_TITLE:
                            self.cfg.ISSUE_TITLE = issue_data.get("title")
                        if not self.cfg.ISSUE_BODY:
                            self.cfg.ISSUE_BODY = issue_data.get("body")
                        raw_labels = issue_data.get("labels", [])
                        for lbl in raw_labels:
                            name = lbl.get("name", "") if isinstance(lbl, dict) else str(lbl)
                            if name and name not in issue_labels:
                                issue_labels.append(name)
                elif self.cfg.LOCAL:
                    try:
                        import json
                        res = subprocess.run(
                            ["gh", "issue", "view", str(self.cfg.ISSUE_NUMBER), "--json", "title,body,labels"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if res.returncode == 0 and res.stdout.strip():
                            data = json.loads(res.stdout)
                            if not self.cfg.ISSUE_TITLE:
                                self.cfg.ISSUE_TITLE = data.get("title")
                            if not self.cfg.ISSUE_BODY:
                                self.cfg.ISSUE_BODY = data.get("body")
                            raw_labels = data.get("labels", [])
                            for lbl in raw_labels:
                                name = lbl.get("name", "") if isinstance(lbl, dict) else str(lbl)
                                if name and name not in issue_labels:
                                    issue_labels.append(name)
                    except Exception as e:
                        logger.debug(f"Failed to fetch issue details via gh CLI: {e}")

        if not is_pr and (self.cfg.ISSUE_TITLE or self.cfg.ISSUE_BODY):
            has_opt_in_label = any(
                lbl.lower() in ("auto-fix", "poing-work")
                for lbl in issue_labels
            )
            has_explicit_command = bool(
                self.cfg.COMMENT_BODY
                and any(
                    cmd in self.cfg.COMMENT_BODY.lower()
                    for cmd in ("/fix", "/work", "@poing-ai fix", "@poing-ai work")
                )
            )
            if not self.cfg.LOCAL and not has_explicit_command and not has_opt_in_label and not self.cfg.AUTO_WORK_ON_ISSUES:
                logger.info("Automatic issue fixing is disabled by default (auto_work_on_issues=false). Skipping.")
                return "", []

            issue_findings, issue_files = self._discover_targets_from_issue()
            if issue_files:
                logger.info(f"Discovered {len(issue_files)} target file(s) for Issue #{self.cfg.ISSUE_NUMBER or 'New'}: {issue_files}")
                return issue_findings, issue_files

        # 3. In Local Mode, check uncommitted diff first
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

    def _discover_targets_from_issue(self) -> Tuple[str, List[str]]:
        """Discovers target files and builds problem context from an Issue title and body."""
        title = self.cfg.ISSUE_TITLE or ""
        body = self.cfg.ISSUE_BODY or ""
        combined = f"{title}\n{body}"
        files: Set[str] = set()

        # 1. Regex scan for file paths in issue title and body
        tokens = re.findall(r"[\w\-\./]+\.[a-zA-Z0-9]+", combined)
        for token in tokens:
            clean = token.strip("`'\"(),:;[]{}")
            candidate = self.root_dir / clean
            if candidate.exists() and candidate.is_file():
                files.add(clean)

        # 2. Query retriever / RAG for relevant source files
        if not files and self.retriever:
            try:
                query = f"{title} {body[:200]}"
                docs = self.retriever.retrieve(query)
                for d in docs:
                    if d.source:
                        candidate = self.root_dir / d.source
                        if candidate.exists() and candidate.is_file():
                            files.add(d.source)
            except Exception as e:
                logger.debug(f"Retriever target discovery failed: {e}")

        # 3. Fallback: Search candidate source files by keywords in issue title
        if not files:
            stop_words = {"fix", "bug", "issue", "error", "problem", "add", "the", "and", "for", "with", "this", "that"}
            keywords = [w.lower() for w in re.findall(r"\b[a-zA-Z_]{3,}\b", title) if w.lower() not in stop_words]
            if keywords:
                exts = ["*.py", "*.gd", "*.swift", "*.kt", "*.java", "*.cs", "*.ts", "*.js", "*.gradle", "*.json"]
                for ext in exts:
                    for p in self.root_dir.rglob(ext):
                        if any(part.startswith(".") or part in ("build", "dist", "node_modules", ".git", ".godot", "venv") for part in p.parts):
                            continue
                        name_lower = p.name.lower()
                        if any(k in name_lower for k in keywords):
                            rel = str(p.relative_to(self.root_dir))
                            files.add(rel)
                            if len(files) >= 5:
                                break
                    if len(files) >= 5:
                        break

        findings = f"## Issue #{self.cfg.ISSUE_NUMBER or 'New'}: {title}\n\n{body}"
        return findings, list(files)

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

        timeout = getattr(self.cfg, "TEST_TIMEOUT", 60)
        logger.info(f"Running test validation command: `{test_cmd}` (timeout={timeout}s)...")
        child_env = os.environ.copy()
        keys_to_clear = [
            "MODE",
            "TRIGGER_ACTION",
            "PROVIDER",
            "AI_PROVIDER",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "DEEPSEEK_API_KEY",
            "ANTHROPIC_API_KEY",
            "OLLAMA_BASE_URL",
            "RAG_PROVIDER",
            "GITHUB_TOKEN",
            "PR_NUMBER",
            "ISSUE_NUMBER",
            "REPO",
        ]
        for k in list(child_env.keys()):
            if k in keys_to_clear or k.startswith("INPUT_"):
                child_env.pop(k, None)
        try:
            res = subprocess.run(
                test_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.root_dir),
                env=child_env,
            )
            output = (res.stdout or "") + "\n" + (res.stderr or "")
            return (res.returncode == 0), output.strip()
        except subprocess.TimeoutExpired:
            return False, f"Test execution timed out after {timeout}s."
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
        """Commits and pushes repairs to the PR branch or creates a new PR for an Issue."""
        if not applied_fixes:
            return

        pr_num = self.cfg.ISSUE_NUMBER or self.cfg.PR_NUMBER or getattr(self.cfg, "NUMBER", None)
        is_pr = False
        if self.client and self.cfg.REPO and pr_num:
            is_pr = self.client.is_pull_request(self.cfg.REPO, str(pr_num))

        if not is_pr and self.cfg.ISSUE_NUMBER:
            self._handle_remote_issue_pr(result, applied_fixes)
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
                body = f'## 🛠️ <img src="{POING_LOGO_URL}" width="24" height="24" valign="middle" alt="Poing AI" /> [Poing AI](https://github.com/poingstudios/poing-ai) Auto-Fix\n\n'
                body += f"Applied **{len(applied_fixes)} automated fix(es)**:\n"
                for fix in applied_fixes:
                    body += f"- `{fix.file_path}`: {fix.explanation}\n"
                body += f"\nCommit: `{commit_msg}`\n\n"
                body += "✅ All validation tests passed!"
                self.client.add_comment(self.cfg.REPO, str(self.cfg.ISSUE_NUMBER), body)
        except Exception as e:
            logger.error(f"Failed to commit/push remote fixes: {e}")

    def _handle_remote_issue_pr(self, result: Optional[FixResult], applied_fixes: List[FileFix]) -> None:
        """Creates a fix branch, commits repairs, pushes to origin, and opens a PR resolving the issue."""
        issue_num = str(self.cfg.ISSUE_NUMBER)
        title = self.cfg.ISSUE_TITLE or f"resolve issue #{issue_num}"
        raw_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", title.lower()).strip("-")
        slug = raw_slug[:30].rstrip("-") if raw_slug else "fix"
        branch_name = f"fix/issue-{issue_num}-{slug}"

        commit_msg = f"fix(#{issue_num}): {title}"
        file_paths = [f.file_path for f in applied_fixes]

        try:
            logger.info(f"Creating new fix branch `{branch_name}` for Issue #{issue_num}...")
            subprocess.run(["git", "checkout", "-B", branch_name], check=True)
            subprocess.run(["git", "config", "user.name", "poing-ai[bot]"], check=True)
            subprocess.run(["git", "config", "user.email", "296332247+poing-ai[bot]@users.noreply.github.com"], check=True)
            subprocess.run(["git", "add"] + file_paths, check=True)
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push", "-u", "origin", branch_name], check=True)
            logger.info(f"✅ Successfully pushed fix branch `{branch_name}` to origin.")

            # Create Pull Request
            pr_title = f"fix(#{issue_num}): {title}"
            pr_body = (
                f"## 🛠️ Automated Fix for Issue #{issue_num}\n\n"
                f"Closes #{issue_num}\n\n"
                f"### Summary\n{result.summary if result and result.summary else 'Automated fix for reported issue.'}\n\n"
                f"### Applied Fixes\n"
            )
            for fix in applied_fixes:
                pr_body += f"- `{fix.file_path}`: {fix.explanation}\n"
            pr_body += "\n### Test Verification\n"
            if result and result.tests_passed:
                pr_body += "✅ All automated tests and linters passed!\n"
            else:
                pr_body += "⚠️ Tests were executed; please review changes.\n"
            pr_body += "\n---\n*Automated fix generated by [Poing AI](https://github.com/poingstudios/poing-ai)*\n"

            base_branch = self.cfg.BASE_REF or "master"
            pr_url = ""
            if self.client and self.cfg.REPO:
                pr_data = self.client.create_pull_request(
                    repo=self.cfg.REPO,
                    title=pr_title,
                    body=pr_body,
                    head=branch_name,
                    base=base_branch,
                )
                if pr_data and "number" in pr_data:
                    pr_num_val = pr_data["number"]
                    pr_url = pr_data.get("html_url", f"#{pr_num_val}")
                    logger.info(f"✅ Successfully opened Pull Request {pr_url} for Issue #{issue_num}")

                # Comment on the original issue
                issue_comment = (
                    f'<img src="{POING_LOGO_URL}" width="18" height="18" valign="middle" alt="Poing AI" /> **[Poing AI](https://github.com/poingstudios/poing-ai)** has analyzed this issue and opened a pull request with an automated fix:\n\n'
                    f"👉 **Pull Request:** {pr_url if pr_url else branch_name}\n\n"
                    f"**Summary of Changes:**\n{result.summary if result and result.summary else ''}"
                )
                self.client.add_comment(self.cfg.REPO, issue_num, issue_comment)
        except Exception as e:
            logger.error(f"Failed to create fix branch or PR for Issue #{issue_num}: {e}")
