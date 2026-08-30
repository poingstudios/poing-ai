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

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ReviewVerdict(str, Enum):
    APPROVED = "APPROVED"
    APPROVED_WITH_SUGGESTIONS = "APPROVED_WITH_SUGGESTIONS"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class TriagePriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ReviewFinding:
    severity: str  # "🔴", "🟡", "🟢"
    file: str
    finding: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "severity": self.severity,
            "file": self.file,
            "finding": self.finding,
        }


@dataclass
class ReviewComment:
    path: str
    line: int
    body: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "body": self.body,
        }


@dataclass
class ReviewResult:
    verdict: ReviewVerdict = ReviewVerdict.APPROVED
    summary: str = ""
    findings: List[ReviewFinding] = field(default_factory=list)
    comments: List[ReviewComment] = field(default_factory=list)
    model: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "verdict": self.verdict.value if isinstance(self.verdict, ReviewVerdict) else str(self.verdict),
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "comments": [c.to_dict() for c in self.comments],
        }


@dataclass
class TriageResult:
    labels: List[str] = field(default_factory=list)
    priority: TriagePriority = TriagePriority.MEDIUM
    summary: str = ""
    is_duplicate: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "labels": self.labels,
            "priority": self.priority.value if isinstance(self.priority, TriagePriority) else str(self.priority),
            "summary": self.summary,
            "is_duplicate": self.is_duplicate,
        }


@dataclass(frozen=True)
class DependencyUpdate:
    platform: str
    dependency: str
    old_version: str
    new_version: str
    file_path: str
    update_type: str = "MINOR"  # "MAJOR", "MINOR", "PATCH"

    def to_dict(self) -> Dict[str, str]:
        return {
            "platform": self.platform,
            "dependency": self.dependency,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "file_path": self.file_path,
            "update_type": self.update_type,
        }


@dataclass
class SyncSummary:
    has_updates: bool = False
    updates: List[DependencyUpdate] = field(default_factory=list)
    summary_table: str = ""
    changelog_notes: str = ""


@dataclass
class FileFix:
    file_path: str
    explanation: str
    original_snippet: str
    replacement_snippet: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "file_path": self.file_path,
            "explanation": self.explanation,
            "original_snippet": self.original_snippet,
            "replacement_snippet": self.replacement_snippet,
        }


@dataclass
class FixResult:
    summary: str = ""
    fixes: List[FileFix] = field(default_factory=list)
    model: str = ""
    tests_passed: bool = True
    test_output: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "summary": self.summary,
            "fixes": [f.to_dict() for f in self.fixes],
            "model": self.model,
            "tests_passed": self.tests_passed,
            "test_output": self.test_output,
        }
