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


def build_fix_prompt(
    findings_context: str,
    target_files: Dict[str, str],
    rag_guidelines: str = "",
    engine_rules: str = "",
    test_failure_trace: Optional[str] = None,
) -> str:
    """Builds the prompt instructing AI agent to generate exact code repairs."""
    prompt = """You are an Autonomous Software Engineer AI Agent specializing in automated bug fixing, architectural compliance, and test-driven repairs.

### TASK:
Analyze the issues, review findings, or test failures reported below and generate precise, minimal, and correct code replacements to resolve them.

### REPAIR RULES:
1. **Precision & Drop-in Replacement**:
   - For every change, provide an `original_snippet` that EXACTLY matches the existing text in the target file (including whitespace and indentation).
   - Provide the corresponding `replacement_snippet` that cleanly replaces `original_snippet`.
   - Never replace the whole file if a localized snippet replacement is sufficient.
2. **Architectural & Engine Standards**:
   - Strictly follow the repository guidelines and game engine rules provided below.
   - Maintain idiomatic patterns (e.g., Godot GDScript `:=` typing, memory management, safe error handling).
3. **Preserve Functionality**:
   - Do not remove existing logic or tests unless directly requested or required to fix the vulnerability/bug.
   - Keep comments and docstrings intact.
4. **Safety & Security**:
   - Ensure all input sanitization, command execution, or memory allocation is secure.
"""

    if engine_rules.strip():
        prompt += f"\n### ENGINE & FRAMEWORK GUIDELINES:\n{engine_rules.strip()}\n"

    if rag_guidelines.strip():
        prompt += f"\n### REPOSITORY ARCHITECTURAL GUIDELINES (RAG Context):\n{rag_guidelines.strip()}\n"

    prompt += f"\n### ISSUES / REVIEW FINDINGS TO RESOLVE:\n{findings_context.strip()}\n"

    if test_failure_trace:
        prompt += f"\n### PREVIOUS TEST RUN ERROR TRACE (Fix this failure):\n```\n{test_failure_trace.strip()}\n```\n"

    prompt += "\n### TARGET FILES CONTENT:\n"
    for file_path, content in target_files.items():
        prompt += f"\n--- START OF FILE: `{file_path}` ---\n{content}\n--- END OF FILE: `{file_path}` ---\n"

    prompt += """
### JSON RESPONSE SCHEMA:
You MUST respond with valid JSON matching this structure:
{
  "summary": "Concise summary of the fixes applied",
  "fixes": [
    {
      "file_path": "path/to/file.ext",
      "explanation": "Why this change fixes the issue",
      "original_snippet": "exact lines from target file to replace",
      "replacement_snippet": "new lines to insert in place of original_snippet"
    }
  ]
}
"""
    return prompt
