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
from poing_ai.ai.openai_compatible import sanitize_ai_json_output
from poing_ai.core.logging import get_logger
from poing_ai.core.models import (
    ReviewComment,
    ReviewFinding,
    ReviewResult,
    ReviewVerdict,
    TriagePriority,
    TriageResult,
)

logger = get_logger("ai.ollama")

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODELS = [
    "deepseek-r1:latest",
    "deepseek-coder:6.7b",
    "qwen2.5-coder:7b",
    "llama3.3:latest",
    "llama3:latest",
    "codellama:latest",
]

PREFERRED_MODEL_KEYWORDS = [
    "deepseek-r1",
    "deepseek-coder",
    "qwen2.5-coder",
    "qwen-coder",
    "codellama",
    "starcoder",
    "llama3.3",
    "llama3.2",
    "llama3.1",
    "llama3",
    "mistral",
    "gemma",
]


class OllamaProvider(BaseAIProvider):
    """Native AI Provider for local Ollama instances with automatic local model discovery."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        models_to_try: Optional[List[str]] = None,
    ):
        raw_base = base_url or DEFAULT_OLLAMA_HOST
        self.base_url = raw_base.rstrip("/").removesuffix("/v1").removesuffix("/api")
        self._custom_models = models_to_try is not None
        self.models_to_try = models_to_try or DEFAULT_OLLAMA_MODELS

    def is_available(self) -> bool:
        """Checks if the local Ollama daemon is reachable."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def get_installed_models(self) -> List[str]:
        """Queries Ollama for currently installed/pulled models."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            pass
        return []

    def _resolve_models_to_try(self, model_name: Optional[str] = None) -> List[str]:
        if model_name:
            return [model_name]

        if self._custom_models:
            return self.models_to_try

        installed = self.get_installed_models()
        if not installed:
            return self.models_to_try

        # Sort installed models prioritizing coding and reasoning models
        def score_model(name: str) -> int:
            lower = name.lower()
            for idx, kw in enumerate(PREFERRED_MODEL_KEYWORDS):
                if kw in lower:
                    return idx
            return len(PREFERRED_MODEL_KEYWORDS)

        sorted_installed = sorted(installed, key=score_model)
        logger.info(f"Discovered installed Ollama models: {sorted_installed}")
        return sorted_installed

    def _call_model(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str = "You are a senior code reviewer. Output strictly valid JSON.",
        temperature: float = 0.2,
        require_json: bool = True,
    ) -> Optional[str]:
        url = f"{self.base_url}/api/chat"
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if require_json:
            payload["format"] = "json"

        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, timeout=300)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("message", {}).get("content", "")
                    return content.strip() if content.strip() else None

                if resp.status_code == 404:
                    logger.error(
                        f"Model '{model_name}' not found in Ollama. "
                        f"Try pulling it with: `ollama pull {model_name}`"
                    )
                    return None

                logger.error(f"Ollama error ({model_name}): {resp.status_code} {resp.text}")
                return None
            except requests.exceptions.ConnectionError:
                logger.error(
                    f"Could not connect to Ollama at {self.base_url}. "
                    "Make sure Ollama is running (`ollama serve`)."
                )
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Request to Ollama failed for {model_name}: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt * 2)
                    continue
                return None

        return None

    def _parse_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        cleaned = sanitize_ai_json_output(raw_text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            logger.error(f"Failed to parse JSON response from Ollama: {raw_text[:400]}")
            return None

    def generate_review(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        models = self._resolve_models_to_try(model_name)
        for model in models:
            logger.info(f"Generating review using Ollama model {model}...")
            raw = self._call_model(
                prompt=prompt,
                model_name=model,
                system_prompt="You are Poing AI. Return a JSON object with verdict (APPROVED, APPROVED_WITH_SUGGESTIONS, CHANGES_REQUESTED), summary, findings, and comments.",
                temperature=0.2,
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
        models = self._resolve_models_to_try(model_name)
        for model in models:
            logger.info(f"Generating triage using Ollama model {model}...")
            raw = self._call_model(
                prompt=prompt,
                model_name=model,
                system_prompt="You are an issue triage assistant. Return a JSON object with labels, priority (high, medium, low), summary, and is_duplicate.",
                temperature=0.1,
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
        models = self._resolve_models_to_try(model_name)
        for model in models:
            logger.info(f"Generating changelog summary using Ollama model {model}...")
            raw = self._call_model(
                prompt=prompt,
                model_name=model,
                system_prompt="You are a release manager generating clean changelog summaries.",
                temperature=0.2,
                require_json=False,
            )
            if raw:
                return sanitize_ai_json_output(raw)
        return None
