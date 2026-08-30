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

import re
from dataclasses import dataclass
from typing import List


@dataclass
class MarkdownSection:
    breadcrumb: str
    content: str
    header_level: int = 1


def parse_markdown_with_breadcrumbs(filename: str, markdown_text: str, max_chunk_chars: int = 2500) -> List[MarkdownSection]:
    """Parses a Markdown document into logical sections preserving the heading hierarchy breadcrumb.

    Example breadcrumb: [AGENTS.md > Coding Standards > GDScript Rules]
    """
    lines = markdown_text.splitlines()
    sections: List[MarkdownSection] = []

    # Stack of (level, title)
    header_stack: List[tuple[int, str]] = []
    current_lines: List[str] = []

    def flush_section():
        if not current_lines:
            return
        body = "\n".join(current_lines).strip()
        if not body:
            return

        breadcrumb_parts = [filename] + [title for _, title in header_stack]
        breadcrumb_str = " > ".join(breadcrumb_parts)

        # If body is within max chunk size, save as a single section
        if len(body) <= max_chunk_chars:
            sections.append(MarkdownSection(
                breadcrumb=f"[{breadcrumb_str}]",
                content=f"### Context: [{breadcrumb_str}]\n\n{body}",
                header_level=header_stack[-1][0] if header_stack else 1,
            ))
        else:
            # Sub-split long sections without breaking code fences if possible
            for i in range(0, len(body), max_chunk_chars - 200):
                chunk = body[i : i + max_chunk_chars]
                sections.append(MarkdownSection(
                    breadcrumb=f"[{breadcrumb_str}]",
                    content=f"### Context: [{breadcrumb_str}]\n\n{chunk}",
                    header_level=header_stack[-1][0] if header_stack else 1,
                ))

    header_regex = re.compile(r"^(#{1,6})\s+(.*)$")

    for line in lines:
        match = header_regex.match(line)
        if match:
            flush_section()
            current_lines = []

            hashes, title = match.group(1), match.group(2).strip()
            level = len(hashes)

            # Pop headers of equal or deeper level
            while header_stack and header_stack[-1][0] >= level:
                header_stack.pop()

            header_stack.append((level, title))
        else:
            current_lines.append(line)

    flush_section()
    return sections
