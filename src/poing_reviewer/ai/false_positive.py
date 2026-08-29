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
from typing import Any, Dict, List, Optional, Set, Tuple

from poing_reviewer.core.config import COMMENT_FOOTER_HINT, FP_KEYWORDS, fingerprint
from poing_reviewer.core.logging import get_logger
from poing_reviewer.core.models import ReviewComment, ReviewFinding

logger = get_logger("ai.false_positive")


def strip_footer(body: str) -> str:
    idx = body.rfind("\n\n---\n")
    if idx != -1:
        return body[:idx].strip()
    return body.strip()


def add_footer_hint(body: str) -> str:
    return body.rstrip() + COMMENT_FOOTER_HINT


def _is_bot_comment_by_login(author_login: str, bot_login: Optional[str]) -> bool:
    if not author_login:
        return False
    if bot_login and author_login.lower() == bot_login.lower():
        return True
    return "bot" in author_login.lower()


def fetch_thumbs_down_fingerprints(threads: List[Dict[str, Any]], bot_login: Optional[str]) -> Set[str]:
    suppressed: Set[str] = set()

    for thread in threads:
        if not thread:
            continue
        comments = (thread.get("comments") or {}).get("nodes") or []
        for comment in comments:
            if not comment:
                continue
            author_login = (comment.get("author") or {}).get("login", "")
            if not _is_bot_comment_by_login(author_login, bot_login):
                continue

            reactions = (comment.get("reactions") or {}).get("nodes") or []
            has_thumbs_down = any(r.get("content") == "THUMBS_DOWN" for r in reactions)
            if not has_thumbs_down:
                continue

            body = strip_footer(comment.get("body", ""))
            path = thread.get("path", "")
            line = thread.get("line")
            fp = fingerprint(path, body, line)
            suppressed.add(fp)

    if suppressed:
        logger.info(f"Found {len(suppressed)} previously 👎'd comment(s) to suppress")

    return suppressed


def is_suppressed(comment_body: str, path: str, line: Optional[int], suppressed_fingerprints: Set[str]) -> bool:
    clean_body = strip_footer(comment_body)
    fp = fingerprint(path, clean_body, line)
    return fp in suppressed_fingerprints


def filter_action_version_false_positives(
    findings: List[ReviewFinding],
    comments: List[ReviewComment],
    verified_actions: Optional[Dict[str, bool]] = None,
) -> Tuple[List[ReviewFinding], List[ReviewComment]]:
    if not verified_actions:
        return findings, comments

    valid_actions = {k for k, v in verified_actions.items() if v}
    if not valid_actions:
        return findings, comments

    fp_action_phrases = [
        "non-existent",
        "does not exist",
        "latest version is",
        "not exist",
        "invalid version",
        "unrecognized",
        "conflicts with",
    ]

    filtered_findings: List[ReviewFinding] = []
    for f in findings:
        finding_text = f.finding.lower()
        is_fp = False
        for action in valid_actions:
            action_name = action.split("@")[0].lower()
            tag = action.split("@")[-1].lower()
            if (action_name in finding_text or tag in finding_text) and any(
                kw in finding_text for kw in fp_action_phrases
            ):
                logger.info(f"Suppressing false-positive action finding for verified [{action}]: {f.finding}")
                is_fp = True
                break
        if not is_fp:
            filtered_findings.append(f)

    filtered_comments: List[ReviewComment] = []
    for c in comments:
        comment_text = c.body.lower()
        is_fp = False
        for action in valid_actions:
            action_name = action.split("@")[0].lower()
            tag = action.split("@")[-1].lower()
            if (action_name in comment_text or tag in comment_text) and any(
                kw in comment_text for kw in fp_action_phrases
            ):
                logger.info(f"Suppressing false-positive action comment for verified [{action}]: {c.body}")
                is_fp = True
                break
        if not is_fp:
            filtered_comments.append(c)

    return filtered_findings, filtered_comments


SPECULATIVE_PATTERNS = [
    re.compile(r"ensure (?:that )?(?:all )?other (?:parts|files|callers|references)", re.IGNORECASE),
    re.compile(r"verify (?:that )?(?:all )?other (?:parts|files|callers|references)", re.IGNORECASE),
    re.compile(r"not (?:shown|visible) in (?:this|the) diff", re.IGNORECASE),
    re.compile(r"make sure (?:this doesn't|it doesn't) break unseen", re.IGNORECASE),
    re.compile(r"check if (?:other|any other) (?:places|files|classes)", re.IGNORECASE),
    re.compile(r"beyond the scope of this diff", re.IGNORECASE),
    re.compile(r"outside of (?:this|the) diff", re.IGNORECASE),
]


def filter_speculative_false_positives(
    findings: List[ReviewFinding],
    comments: List[ReviewComment],
) -> Tuple[List[ReviewFinding], List[ReviewComment]]:
    filtered_findings: List[ReviewFinding] = []
    for f in findings:
        text = f.finding
        if any(pattern.search(text) for pattern in SPECULATIVE_PATTERNS):
            logger.info(f"Suppressing speculative finding: {text[:80]}...")
            continue
        filtered_findings.append(f)

    filtered_comments: List[ReviewComment] = []
    for c in comments:
        text = c.body
        if any(pattern.search(text) for pattern in SPECULATIVE_PATTERNS):
            logger.info(f"Suppressing speculative comment: {text[:80]}...")
            continue
        filtered_comments.append(c)

    return filtered_findings, filtered_comments


def filter_model_false_positives(findings: List[ReviewFinding]) -> List[ReviewFinding]:
    filtered: List[ReviewFinding] = []
    for f in findings:
        finding_lower = f.finding.lower()
        file_lower = f.file.lower()
        text = finding_lower + file_lower
        has_fp_keyword = any(kw in finding_lower for kw in FP_KEYWORDS)
        has_model_ref = any(m in text for m in ["model", "gemini", "gemma"])
        if has_fp_keyword and has_model_ref:
            logger.info(f"Filtering false positive model finding: {f.finding[:80]}")
            continue
        filtered.append(f)
    return filtered
