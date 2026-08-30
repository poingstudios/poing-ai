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

from typing import List
from poing_ai.core.models import DependencyUpdate


CHANGELOG_PROMPT_TEMPLATE = """You are a senior release engineer and dependency manager.
Analyze the following synchronized dependency updates and generate a clear, structured summary in GitHub Markdown for a pull request description.

## Synchronized Updates
{updates_table}

## Raw Release Notes / Metadata
{raw_notes}

## Required Markdown Output Sections:
1. **Summary Table**: Markdown table with columns (Platform, Dependency, Current Version, New Version, Update Type).
2. **Key Changes & Improvements**: High-level highlights of what these updates provide.
3. **⚠️ Breaking Changes & Migration Warnings**: If any MAJOR version bumps or deprecated APIs are detected, highlight them with clear migration guidance.
4. **Compatibility**: Note any required SDK or platform minimum version changes.
"""


def build_changelog_prompt(updates: List[DependencyUpdate], raw_notes: str = "") -> str:
    table_lines = [
        "| Platform | Dependency | Old Version | New Version | Type |",
        "|---|---|---|---|---|",
    ]
    for u in updates:
        table_lines.append(f"| {u.platform} | `{u.dependency}` | {u.old_version} | **{u.new_version}** | `{u.update_type}` |")

    return CHANGELOG_PROMPT_TEMPLATE.format(
        updates_table="\n".join(table_lines),
        raw_notes=raw_notes[:4000] if raw_notes else "No raw release notes provided.",
    )
