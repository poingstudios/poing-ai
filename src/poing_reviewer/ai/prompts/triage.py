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


TRIAGE_PROMPT_TEMPLATE = """You are an issue and pull request triage assistant.

Analyze the following GitHub item and determine:
1. Applicable labels from the available labels list
2. Priority level (high, medium, low)
3. A concise summary (1-2 sentences)
4. Whether this appears to be a duplicate of known issues

## Item Title
{title}

## Item Body
{body}

## Available Labels
{labels}

## Instructions
- Assign ONLY labels that are clearly justified by the title and description.
- Priority:
  - "high": Crash, critical security vulnerability, complete blocker with no workaround.
  - "medium": Regular bugs, feature requests with high value, API additions.
  - "low": Documentation, minor formatting, cosmetic tweaks, non-critical enhancements.
- Return valid JSON matching the schema.
"""


def build_triage_prompt(title: str, body: str, available_labels: List[str]) -> str:
    labels_str = "\n".join(f"- {label}" for label in available_labels)
    return TRIAGE_PROMPT_TEMPLATE.format(
        title=title,
        body=body[:4000] if body else "(No body provided)",
        labels=labels_str,
    )
