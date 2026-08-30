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

import json
import time
from typing import Any, Dict, List, Optional
import requests

from poing_ai.ai.base import BaseAIProvider
from poing_ai.core.logging import get_logger
from poing_ai.core.models import (
    FileFix,
    FixResult,
    ReviewComment,
    ReviewFinding,
    ReviewResult,
    ReviewVerdict,
    TriagePriority,
    TriageResult,
)

logger = get_logger("ai.gemini")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

REVIEW_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "verdict": {
            "type": "STRING",
            "enum": ["APPROVED", "APPROVED_WITH_SUGGESTIONS", "CHANGES_REQUESTED"],
        },
        "summary": {
            "type": "STRING",
            "description": "One or two sentences describing what this PR changes.",
        },
        "findings": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "severity": {
                        "type": "STRING",
                        "enum": ["🔴", "🟡", "🟢"],
                    },
                    "file": {"type": "STRING"},
                    "finding": {"type": "STRING"},
                },
                "required": ["severity", "file", "finding"],
            },
        },
        "comments": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "path": {
                        "type": "STRING",
                        "description": "Relative file path of the code line",
                    },
                    "line": {
                        "type": "INTEGER",
                        "description": "Line number in the new version of the file",
                    },
                    "body": {
                        "type": "STRING",
                        "description": "The review comment for this specific line of code",
                    },
                },
                "required": ["path", "line", "body"],
            },
        },
    },
    "required": ["verdict", "summary", "findings", "comments"],
}

TRIAGE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "labels": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "List of applicable labels",
        },
        "priority": {
            "type": "STRING",
            "enum": ["high", "medium", "low"],
            "description": "Priority level for the issue/PR",
        },
        "summary": {
            "type": "STRING",
            "description": "Brief 1-2 sentence summary",
        },
        "is_duplicate": {
            "type": "BOOLEAN",
            "description": "Whether this issue is likely a duplicate",
        },
    },
    "required": ["labels", "priority", "summary", "is_duplicate"],
}

FIX_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {
            "type": "STRING",
            "description": "Concise summary of the fixes applied.",
        },
        "fixes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "file_path": {"type": "STRING"},
                    "explanation": {"type": "STRING"},
                    "original_snippet": {"type": "STRING"},
                    "replacement_snippet": {"type": "STRING"},
                },
                "required": [
                    "file_path",
                    "explanation",
                    "original_snippet",
                    "replacement_snippet",
                ],
            },
        },
    },
    "required": ["summary", "fixes"],
}


class GeminiProvider(BaseAIProvider):
    def __init__(self, api_key: str, models_to_try: Optional[List[str]] = None):
        self.api_key = api_key
        self.models_to_try = models_to_try or [
            "gemini-2.5-flash",
            "gemini-3.7-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemma-4-31b-it",
        ]
        self.last_used_model = self.models_to_try[0] if self.models_to_try else "gemini-3.7-flash"

    def _call_model(
        self,
        prompt: str,
        model_name: str,
        generation_config: Optional[Dict[str, Any]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        self.last_used_model = model_name
        url = GEMINI_API_URL.format(model=model_name)

        config: Dict[str, Any] = {
            "temperature": 0.2,
        }
        if generation_config:
            config.update(generation_config)

        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": config,
        }

        if response_schema:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            # Gemma models on AI Studio do not support strict responseSchema
            if "gemma" not in model_name.lower():
                payload["generationConfig"]["responseSchema"] = response_schema

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        for attempt in range(3):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=45,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "candidates" not in data or not data["candidates"]:
                        logger.error(f"Unexpected response ({model_name}): {json.dumps(data, indent=2)}")
                        return None
                    parts = data["candidates"][0]["content"]["parts"]
                    feedback = ""
                    for part in parts:
                        if not part.get("thought", False):
                            feedback += part.get("text", "")
                    return feedback.strip() if feedback.strip() else None

                if resp.status_code in (429, 503) and attempt < 2:
                    wait = 3 * (attempt + 1)
                    logger.warning(f"Model {model_name} busy ({resp.status_code}), retry in {wait}s...")
                    time.sleep(wait)
                    continue

                logger.error(f"API error ({model_name}): {resp.status_code} {resp.text}")
                return None
            except requests.exceptions.Timeout:
                logger.warning(f"Model {model_name} timed out after 45s. Failing over to next fallback model...")
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for {model_name}: {e}")
                if attempt < 2:
                    time.sleep(2)
                    continue
                return None
        return None

    def _parse_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        try:
            raw = raw_text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            return json.loads(raw.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {raw_text[:400]}")
            return None

    def generate_review(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        models = [model_name] if model_name else self.models_to_try
        for model in models:
            logger.info(f"Generating review using {model}...")
            raw = self._call_model(
                prompt,
                model,
                generation_config={"temperature": 0.2},
                response_schema=REVIEW_SCHEMA,
            )
            if not raw:
                continue
            data = self._parse_json(raw)
            if not data or "verdict" not in data:
                continue

            findings = [
                ReviewFinding(
                    severity=f.get("severity", "🟡"),
                    file=f.get("file", ""),
                    finding=f.get("finding", ""),
                )
                for f in data.get("findings", [])
            ]
            comments = [
                ReviewComment(
                    path=c.get("path", ""),
                    line=int(c.get("line", 1)),
                    body=c.get("body", ""),
                )
                for c in data.get("comments", [])
            ]
            verdict_str = data.get("verdict", "APPROVED")
            try:
                verdict = ReviewVerdict(verdict_str)
            except ValueError:
                verdict = ReviewVerdict.APPROVED

            self.last_used_model = model
            return ReviewResult(
                verdict=verdict,
                summary=data.get("summary", ""),
                findings=findings,
                comments=comments,
                model=model,
            )
        return None

    def generate_triage(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[TriageResult]:
        models = [model_name] if model_name else self.models_to_try
        for model in models:
            logger.info(f"Generating triage using {model}...")
            raw = self._call_model(
                prompt,
                model,
                generation_config={"temperature": 0.1, "maxOutputTokens": 1024},
                response_schema=TRIAGE_SCHEMA,
            )
            if not raw:
                continue
            data = self._parse_json(raw)
            if not data or "priority" not in data:
                continue

            p_str = data.get("priority", "medium").lower()
            try:
                priority = TriagePriority(p_str)
            except ValueError:
                priority = TriagePriority.MEDIUM

            self.last_used_model = model
            return TriageResult(
                labels=data.get("labels", []),
                priority=priority,
                summary=data.get("summary", ""),
                is_duplicate=data.get("is_duplicate", False),
            )
        return None

    def generate_changelog_summary(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[str]:
        models = [model_name] if model_name else self.models_to_try
        for model in models:
            logger.info(f"Generating changelog summary using {model}...")
            raw = self._call_model(
                prompt,
                model,
                generation_config={"temperature": 0.2, "maxOutputTokens": 2048},
            )
            if raw:
                self.last_used_model = model
                return raw
        return None

    def generate_fix(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[FixResult]:
        models = [model_name] if model_name else self.models_to_try
        for model in models:
            logger.info(f"Generating automated fix using {model}...")
            raw = self._call_model(
                prompt,
                model,
                response_schema=FIX_SCHEMA,
                generation_config={"temperature": 0.2},
            )
            if not raw:
                continue
            data = self._parse_json(raw)
            if not data or "fixes" not in data:
                continue

            fixes = [
                FileFix(
                    file_path=f.get("file_path", ""),
                    explanation=f.get("explanation", ""),
                    original_snippet=f.get("original_snippet", ""),
                    replacement_snippet=f.get("replacement_snippet", ""),
                )
                for f in data.get("fixes", [])
                if f.get("file_path") and f.get("original_snippet") is not None and f.get("replacement_snippet") is not None
            ]
            self.last_used_model = model
            return FixResult(
                summary=data.get("summary", ""),
                fixes=fixes,
                model=self.last_used_model,
                tests_passed=True,
            )
        return None
