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

from typing import Dict, Optional


def build_review_prompt(
    pr_title: str,
    annotated_diff: str,
    guidelines: str = "",
    engine_guidelines: str = "",
    batch_label: str = "",
    verified_actions: Optional[Dict[str, bool]] = None,
    file_contents: Optional[Dict[str, str]] = None,
) -> str:
    action_info = ""
    if verified_actions:
        valid_list = [f"- `{k}`: VALID (Verified live release/tag on GitHub)" for k, v in verified_actions.items() if v]
        invalid_list = [f"- `{k}`: INVALID (Not found on GitHub)" for k, v in verified_actions.items() if not v]
        lines = []
        if valid_list:
            lines.append("### Verified Action Versions (Live GitHub API Check):")
            lines.extend(valid_list)
            lines.append("\nCRITICAL: The actions marked VALID above have been confirmed to exist on GitHub. Do NOT claim they do not exist, and do NOT request changes for these valid versions.")
        if invalid_list:
            lines.append("### Unverified/Non-Existent Actions:")
            lines.extend(invalid_list)
        if lines:
            action_info = "\n## GitHub Actions Ground Truth\n" + "\n".join(lines) + "\n"

    files_context = ""
    if file_contents:
        files_blocks = []
        for fpath, content in file_contents.items():
            files_blocks.append(f"### Full File: `{fpath}`\n```\n{content}\n```")
        if files_blocks:
            files_context = (
                "\n## Full Source Code of Modified Files (Ground Truth)\n"
                "Use the full file contents below to verify class declarations, method implementations, and symbol references across the whole file. Never speculate about code you cannot see in the diff—verify against this full file source.\n\n"
                + "\n\n".join(files_blocks)
                + "\n"
            )

    engine_section = ""
    if engine_guidelines:
        engine_section = f"\n## Engine Specific Guidelines\n{engine_guidelines}\n"

    prompt = f"""You are Poing AI, a senior code reviewer.
Analyze the pull request diff and full file context below, and return a structured JSON response.

PR Title: {pr_title}

## Review Focus

1. **Logic errors and bugs** - Null dereferences, broken state machines, resource leaks, incorrect API usage
2. **Security vulnerabilities** - Secret leaks, injection, insecure permissions
3. **Architecture & parity** - API parity, platform bridge integrity, clean separation of concerns
4. **Reliability & error handling** - Unhandled exception paths, failed async states

{batch_label}

## Strict Quality Rules (No Nitpicks, No Speculation)

1. **GROUND TRUTH FIRST**: You are provided with both the `Annotated Diff` (what changed) and `Full Source Code of Modified Files` (the entire current file). Use the full file content to verify whether functions, variables, or constants are used before making any claims.
2. **NO SPECULATION**: NEVER post speculative comments such as "Please ensure other parts of the file/codebase don't use this", "make sure this doesn't break unseen code", or "not shown in this diff". If you do not see a definite bug in the provided context, do NOT comment.
3. **NO NITPICKS**: Do NOT comment on personal style preferences, trivial formatting, or comments.
4. **EMPTY IS FINE**: If the changes are clean and correct, return `{{"verdict": "APPROVED", "summary": "...", "findings": [], "comments": []}}`. Do NOT invent issues.
5. **EXACT LINE MATCHING**: Inline comments must specify the exact line number from the `Annotated Diff` prefixed with `[<file> L<number>]`.
6. **BACKTICK CODE & HTML TAGS**: Always enclose all HTML tags (e.g. `<details>`, `<summary>`, `<div>`), function names, types, and code symbols in backticks to prevent raw HTML rendering issues in Markdown.

## Output format

Return valid JSON with:
- `verdict`: APPROVED | APPROVED_WITH_SUGGESTIONS | CHANGES_REQUESTED
- `summary`: 1-2 sentence summary of what the PR does
- `findings`: array of {{severity: "🔴"|"🟡"|"🟢", file: "path", finding: "description"}} (can be empty)
- `comments`: array of {{path, line, body}} for inline review notes (can be empty)

{guidelines}
{engine_section}
{action_info}
{files_context}
## Annotated Diff

```diff
{annotated_diff}
```"""
    return prompt
