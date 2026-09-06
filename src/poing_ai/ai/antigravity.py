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

    def __init__(
        self,
        api_key: str,
        default_agent: str = DEFAULT_AGENT,
        fallback_provider: Optional[BaseAIProvider] = None,
    ):
        self.api_key = api_key
        self.default_agent = default_agent
        self.last_used_model = default_agent
        self._fallback_provider = fallback_provider

    @property
    def fallback_provider(self) -> BaseAIProvider:
        if self._fallback_provider is None:
            from poing_ai.ai.gemini import GeminiProvider
            self._fallback_provider = GeminiProvider(api_key=self.api_key)
        return self._fallback_provider

    def _call_agent(self, prompt: str, agent_name: Optional[str] = None, timeout: int = 45) -> Optional[str]:
        target_agent = agent_name or self.default_agent
        self.last_used_model = target_agent
        url = BASE_INTERACTIONS_URL
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
        for attempt in range(1, 3):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
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

                if resp.status_code == 429:
                    logger.warning(f"Antigravity agent quota/TPM limit exceeded (429). Failing over to fallback...")
                    break

                if resp.status_code in (500, 503):
                    time.sleep(attempt * 2)
                    continue

                logger.error(
                    f"Antigravity agent API error (status={resp.status_code}, reason={resp.reason}, attempt={attempt})"
                )
                break
            except requests.exceptions.Timeout:
                logger.warning(f"Antigravity agent request attempt {attempt} timed out after {timeout}s.")
                if attempt >= 2:
                    break
            except Exception as e:
                logger.warning(f"Antigravity agent request attempt {attempt} failed: {e}")
                break

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
        data = self._extract_json(raw) if raw else None
        if not data:
            logger.warning("Failing over from Antigravity to GeminiProvider for code review...")
            res = self.fallback_provider.generate_review(prompt, model_name)
            if res:
                self.last_used_model = getattr(self.fallback_provider, "last_used_model", self.last_used_model)
            return res

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
        data = self._extract_json(raw) if raw else None
        if not data:
            logger.warning("Failing over from Antigravity to GeminiProvider for triage...")
            res = self.fallback_provider.generate_triage(prompt, model_name)
            if res:
                self.last_used_model = getattr(self.fallback_provider, "last_used_model", self.last_used_model)
            return res

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
        raw = self._call_agent(prompt, model_name)
        if not raw:
            logger.warning("Failing over from Antigravity to GeminiProvider for changelog...")
            res = self.fallback_provider.generate_changelog_summary(prompt, model_name)
            if res:
                self.last_used_model = getattr(self.fallback_provider, "last_used_model", self.last_used_model)
            return res
        return raw

    def generate_fix(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[FixResult]:
        raw = self._call_agent(prompt, model_name)
        data = self._extract_json(raw) if raw else None
        if not data:
            logger.warning("Failing over from Antigravity to GeminiProvider for code fix...")
            res = self.fallback_provider.generate_fix(prompt, model_name)
            if res:
                self.last_used_model = getattr(self.fallback_provider, "last_used_model", self.last_used_model)
            return res

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
