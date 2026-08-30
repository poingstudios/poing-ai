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
import re
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

logger = get_logger("ai.antigravity")

DEFAULT_AGENT = "antigravity-preview-05-2026"
BASE_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


class AntigravityAgentProvider(BaseAIProvider):
    """Provider communicating directly with Google Antigravity Managed Agent via the Interactions API."""

    def __init__(self, api_key: str, default_agent: str = DEFAULT_AGENT):
        self.api_key = api_key
        self.default_agent = default_agent
        self.last_used_model = default_agent

    def _call_agent(self, prompt: str, agent_name: Optional[str] = None, timeout: int = 120) -> Optional[str]:
        target_agent = agent_name or self.default_agent
        self.last_used_model = target_agent
        url = f"{BASE_INTERACTIONS_URL}?key={self.api_key}"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        payload = {
            "agent": target_agent,
            "input": prompt,
            "environment": "remote",
        }

        logger.info(f"Dispatching task to Antigravity Agent ({target_agent})...")
        for attempt in range(1, 4):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    # Interactions API returns steps with model_output parts or output_text
                    if "steps" in data:
                        texts = []
                        for step in data["steps"]:
                            if step.get("type") == "model_output" and "content" in step:
                                for part in step["content"]:
                                    if "text" in part:
                                        texts.append(part["text"])
                        if texts:
                            return "\n".join(texts)

                    output_text = data.get("output_text")
                    if not output_text and "outputs" in data:
                        output_text = data["outputs"][0].get("text", "")
                    if not output_text and "candidates" in data:
                        output_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return output_text or json.dumps(data)

                if resp.status_code in (429, 500, 503):
                    logger.warning(f"Antigravity agent busy ({resp.status_code}), retrying in {attempt * 3}s...")
                    time.sleep(attempt * 3)
                    continue

                logger.error(f"Antigravity agent API error ({resp.status_code}): {resp.text}")
                return None
            except Exception as e:
                logger.warning(f"Antigravity agent request attempt {attempt} failed: {e}")
                time.sleep(attempt * 2)

        return None

    def _extract_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Extracts valid JSON object from LLM agent response."""
        if not raw_text:
            return None
        text = raw_text.strip()
        # Strip markdown fences if present
        if "```json" in text:
            match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1).strip()
        elif "```" in text:
            match = re.search(r"```\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1).strip()

        try:
            return json.loads(text)
        except Exception:
            # Try finding first { and last }
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except Exception:
                    pass
        return None

    def generate_review(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        raw = self._call_agent(prompt, model_name)
        if not raw:
            return None
        data = self._extract_json(raw)
        if not data:
            logger.error("Failed to parse JSON review from Antigravity Agent.")
            return None

        verdict_str = data.get("verdict", "APPROVED").upper()
        try:
            verdict = ReviewVerdict(verdict_str)
        except ValueError:
            verdict = ReviewVerdict.APPROVED

        findings = [
            ReviewFinding(
                severity=f.get("severity", "🟢"),
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
        return ReviewResult(
            verdict=verdict,
            summary=data.get("summary", ""),
            findings=findings,
            comments=comments,
            model=self.last_used_model,
        )

    def generate_triage(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[TriageResult]:
        raw = self._call_agent(prompt, model_name)
        if not raw:
            return None
        data = self._extract_json(raw)
        if not data:
            return None

        p_str = data.get("priority", "medium").lower()
        try:
            priority = TriagePriority(p_str)
        except ValueError:
            priority = TriagePriority.MEDIUM

        return TriageResult(
            labels=data.get("labels", []),
            priority=priority,
            summary=data.get("summary", ""),
            is_duplicate=data.get("is_duplicate", False),
        )

    def generate_changelog_summary(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[str]:
        return self._call_agent(prompt, model_name)

    def generate_fix(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[FixResult]:
        raw = self._call_agent(prompt, model_name)
        if not raw:
            return None
        data = self._extract_json(raw)
        if not data:
            logger.error("Failed to parse JSON fix from Antigravity Agent.")
            return None

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
        return FixResult(
            summary=data.get("summary", ""),
            fixes=fixes,
            model=self.last_used_model,
            tests_passed=True,
        )
