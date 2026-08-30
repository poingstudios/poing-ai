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
    ReviewComment,
    ReviewFinding,
    ReviewResult,
    ReviewVerdict,
    TriagePriority,
    TriageResult,
)

logger = get_logger("ai.openai_compatible")


def sanitize_ai_json_output(raw_text: str) -> str:
    """Strips reasoning model tags (e.g. <think>...</think>) and markdown code fences."""
    text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


class OpenAICompatibleProvider(BaseAIProvider):
    """AI Provider for OpenAI-compatible REST APIs (OpenAI, DeepSeek, Groq, OpenRouter, vLLM, LM Studio)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        models_to_try: Optional[List[str]] = None,
    ):
        self.api_key = api_key or "dummy"
        base = (base_url or "https://api.openai.com/v1").rstrip("/")
        if not base.endswith("/v1") and not base.endswith("/chat/completions"):
            base = f"{base}/v1"
        self.base_url = base
        self.models_to_try = models_to_try or [
            "gpt-4o-mini",
            "gpt-4o",
            "deepseek-chat",
            "deepseek-reasoner",
        ]

    def _call_model(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str = "You are a code analysis and review engine. Always respond in valid JSON.",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        require_json: bool = True,
    ) -> Optional[str]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if require_json:
            payload["response_format"] = {"type": "json_object"}

        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=90)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        logger.error(f"Empty choices in response ({model_name}): {data}")
                        return None
                    content = choices[0].get("message", {}).get("content", "")
                    return content.strip() if content.strip() else None

                # Fallback if response_format is not supported by endpoint
                if resp.status_code == 400 and require_json and "response_format" in payload:
                    logger.warning(f"Endpoint does not support response_format, retrying without it ({model_name})...")
                    payload.pop("response_format", None)
                    continue

                if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    wait = 2 ** attempt * 3
                    logger.warning(f"Model {model_name} returned {resp.status_code}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                logger.error(f"API error ({model_name}): {resp.status_code} {resp.text}")
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for {model_name}: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt * 3)
                    continue
                return None

        return None

    def _parse_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        cleaned = sanitize_ai_json_output(raw_text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try finding first JSON object substring {...}
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            logger.error(f"Failed to parse JSON response: {raw_text[:400]}")
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
                prompt=prompt,
                model_name=model,
                system_prompt="You are Poing AI. Return a JSON object with verdict, summary, findings, and comments.",
                temperature=0.2,
                max_tokens=4096,
                require_json=True,
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

            return ReviewResult(
                verdict=verdict,
                summary=data.get("summary", ""),
                findings=findings,
                comments=comments,
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
                prompt=prompt,
                model_name=model,
                system_prompt="You are an issue triage assistant. Return a JSON object with labels, priority, summary, and is_duplicate.",
                temperature=0.1,
                max_tokens=1024,
                require_json=True,
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
                prompt=prompt,
                model_name=model,
                system_prompt="You are a release manager generating clean changelog summaries.",
                temperature=0.2,
                max_tokens=2048,
                require_json=False,
            )
            if raw:
                return sanitize_ai_json_output(raw)
        return None
