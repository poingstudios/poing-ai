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

from poing_ai.core.config import COMMENT_FOOTER_HINT, FP_KEYWORDS, fingerprint
from poing_ai.core.logging import get_logger
from poing_ai.core.models import ActionSchema, ReviewComment, ReviewFinding

logger = get_logger("ai.false_positive")


def strip_footer(body: str) -> str:
    idx = body.rfind("\n\n---\n")
    if idx != -1:
        return body[:idx].strip()
    return body.strip()


def add_footer_hint(body: str) -> str:
    return body.rstrip() + COMMENT_FOOTER_HINT


def _is_bot_comment_by_login(author_login: Optional[str], bot_login: Optional[str], body: Optional[str] = "") -> bool:
    login_str = (author_login or "").lower()
    body_str = body or ""
    if bot_login and login_str == bot_login.lower():
        return True
    if "bot" in login_str or "poing-ai" in login_str:
        return True
    if "👍 helpful · 👎 false positive" in body_str or "About Poing AI" in body_str:
        return True
    return False


import difflib


def _normalize_comment_text(text: str) -> str:
    cleaned = strip_footer(text).lower()
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"`.*?`", "", cleaned)
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return " ".join(cleaned.split())


class SuppressionSet(set):
    """Set of suppressed fingerprints with (path, line) and fuzzy text tracking."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locations: Set[Tuple[str, int]] = set()
        self.comment_texts: List[Tuple[str, Optional[int], str]] = []

    def add_suppression(self, path: str, line: Optional[int], body: str, fp: str) -> None:
        self.add(fp)
        if line is not None:
            self.locations.add((path, int(line)))
        self.comment_texts.append((path, line, body))

    def is_suppressed_location(self, path: str, line: Optional[int]) -> bool:
        if line is not None and (path, int(line)) in self.locations:
            return True
        return False

    def is_fuzzy_match(self, path: str, body: str, line: Optional[int] = None, threshold: float = 0.7) -> bool:
        norm_body = _normalize_comment_text(body)
        for prev_path, prev_line, prev_body in self.comment_texts:
            if prev_path == path:
                if line is not None and prev_line is not None and abs(line - prev_line) > 1:
                    continue
                prev_norm = _normalize_comment_text(prev_body)
                if prev_norm == norm_body:
                    return True
                similarity = difflib.SequenceMatcher(None, norm_body, prev_norm).ratio()
                if similarity >= threshold:
                    return True
        return False


def fetch_thumbs_down_fingerprints(threads: List[Dict[str, Any]], bot_login: Optional[str]) -> SuppressionSet:
    suppressed = SuppressionSet()

    for thread in threads:
        if not thread:
            continue
        comments = (thread.get("comments") or {}).get("nodes") or []
        for comment in comments:
            if not comment:
                continue
            author_login = (comment.get("author") or {}).get("login", "")
            raw_body = comment.get("body", "")
            if not _is_bot_comment_by_login(author_login, bot_login, body=raw_body):
                continue

            reactions = (comment.get("reactions") or {}).get("nodes") or []
            has_thumbs_down = any(r.get("content") == "THUMBS_DOWN" for r in reactions)
            if not has_thumbs_down:
                continue

            body = strip_footer(comment.get("body", ""))
            path = thread.get("path", "")
            line = thread.get("line")
            fp = fingerprint(path, body, line)
            suppressed.add_suppression(path, line, body, fp)

    if suppressed:
        logger.info(f"Found {len(suppressed)} previously 👎'd comment(s) to suppress")

    return suppressed


def is_suppressed(comment_body: str, path: str, line: Optional[int], suppressed_fingerprints: Set[str]) -> bool:
    clean_body = strip_footer(comment_body)
    fp = fingerprint(path, clean_body, line)
    if fp in suppressed_fingerprints:
        return True

    if isinstance(suppressed_fingerprints, SuppressionSet):
        if suppressed_fingerprints.is_suppressed_location(path, line):
            return True
        if suppressed_fingerprints.is_fuzzy_match(path, clean_body, line=line):
            return True

    if line is not None:
        if f"{path}:{line}" in suppressed_fingerprints or (path, line) in suppressed_fingerprints:  # type: ignore
            return True

    return False


def filter_suppressed_findings(
    findings: List[ReviewFinding],
    suppressed_locations: Set[Tuple[str, int]],
    suppressed_fps: Set[str],
) -> List[ReviewFinding]:
    filtered: List[ReviewFinding] = []
    for f in findings:
        fp = fingerprint(f.file, f.finding)
        if fp in suppressed_fps:
            logger.info(f"Suppressing finding matching suppressed fingerprint: {f.finding[:80]}")
            continue

        is_loc_suppressed = False
        for path, line in suppressed_locations:
            if f.file == path:
                if re.search(rf"(?:\bL|\bline\s*|:){line}\b", f.finding, re.IGNORECASE):
                    logger.info(f"Suppressing finding for {path}:{line}: {f.finding[:80]}")
                    is_loc_suppressed = True
                    break
        if not is_loc_suppressed:
            filtered.append(f)
    return filtered


def filter_action_version_false_positives(
    findings: List[ReviewFinding],
    comments: List[ReviewComment],
    verified_actions: Optional[Dict[str, Any]] = None,
) -> Tuple[List[ReviewFinding], List[ReviewComment]]:
    if not verified_actions:
        return findings, comments

    valid_actions: Dict[str, Optional[ActionSchema]] = {}
    for k, v in verified_actions.items():
        exists = v.exists if isinstance(v, ActionSchema) else bool(v)
        if exists:
            valid_actions[k] = v if isinstance(v, ActionSchema) else None

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

    fp_input_phrases = [
        "not a valid",
        "not valid",
        "invalid parameter",
        "invalid input",
        "invalid option",
        "does not exist",
        "does not support",
        "doesn't support",
        "doesn't exist",
        "unrecognized input",
        "unrecognized parameter",
        "unrecognized option",
        "unknown parameter",
        "unknown input",
        "unexpected input",
        "unexpected parameter",
        "not recognized",
        "not supported",
        "not accept",
        "unsupported parameter",
        "unsupported input",
        "no such input",
        "no such parameter",
        "fictional",
    ]

    def _is_action_fp(text: str) -> bool:
        text_lower = text.lower()
        for action, schema in valid_actions.items():
            action_name = action.split("@")[0].lower()
            tag = action.split("@")[-1].lower()
            action_repo = action_name.split("/")[-1]

            # 1. Action version / non-existence false positive
            if (action_name in text_lower or tag in text_lower) and any(
                kw in text_lower for kw in fp_action_phrases
            ):
                logger.info(f"Suppressing false-positive action finding/comment for verified [{action}]: {text[:80]}")
                return True

            # 2. Action declared input false positive
            if schema and schema.inputs:
                if action_name in text_lower or action_repo in text_lower:
                    for inp_name in schema.inputs.keys():
                        if inp_name.lower() in text_lower and any(
                            kw in text_lower for kw in fp_input_phrases
                        ):
                            logger.info(
                                f"Suppressing false-positive action input for verified [{action}] declared input [{inp_name}]: {text[:80]}"
                            )
                            return True
        return False

    filtered_findings = [f for f in findings if not _is_action_fp(f.finding)]
    filtered_comments = [c for c in comments if not _is_action_fp(c.body)]

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
