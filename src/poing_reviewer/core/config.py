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

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


FALLBACK_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemma-4-31b-it",
    "gemma-4-26b",
]

OLLAMA_FALLBACK_MODELS = [
    "deepseek-r1:latest",
    "deepseek-coder:6.7b",
    "qwen2.5-coder:7b",
    "llama3.3:latest",
    "codellama:latest",
]


def get_model_max_chars(model_name: str, requested_max: int = 100000) -> int:
    """Returns safe character limit per diff batch based on model token capacity."""
    m = model_name.lower()
    if "gemma" in m:
        # Gemma Free Tier has a strict 16k TPM limit. Safe char limit: ~20,000 chars (~5k tokens)
        return min(requested_max, 20000)
    elif any(k in m for k in ["deepseek-coder:6.7b", "qwen2.5-coder:7b", "codellama", "mistral"]):
        # Small local models with 8k-16k context window
        return min(requested_max, 25000)
    return requested_max

OPENAI_FALLBACK_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "deepseek-chat",
    "deepseek-reasoner",
]

VERDICT_PRIORITY = {
    "CHANGES_REQUESTED": 2,
    "APPROVED_WITH_SUGGESTIONS": 1,
    "APPROVED": 0,
}

VERDICT_MAP = {
    "APPROVED": "**✅ Approved**",
    "APPROVED_WITH_SUGGESTIONS": "**🟡 Approved with suggestions**",
    "CHANGES_REQUESTED": "**🔴 Changes requested**",
}

GITHUB_EVENT_MAP = {
    "APPROVED": "APPROVE",
    "APPROVED_WITH_SUGGESTIONS": "APPROVE",
    "CHANGES_REQUESTED": "REQUEST_CHANGES",
}

FP_KEYWORDS = [
    "invalid", "non-existent", "not found", "does not exist",
    "fictional", "not a valid",
]

COMMENT_FOOTER_HINT = (
    "\n\n---\n"
    "<sub>👍 helpful · 👎 false positive</sub>"
)

TRIAGE_FOOTER = (
    "\n\n---\n"
    "<sub>🤖 Triaged by [Poing Reviewer](https://github.com/poingstudios/poing-reviewer)</sub>"
)

REVIEW_FOOTER = (
    "\n\n---\n"
    "<details>\n"
    "<summary>ℹ️ <b>About Poing Reviewer</b></summary>\n<br>\n\n"
    "[Poing Reviewer](https://github.com/poingstudios/poing-reviewer) is an open-source AI code reviewer and guidelines verifier for Godot, Unity, Unreal, and multi-platform repositories.\n"
    "</details>"
)

AVAILABLE_LABELS = [
    "bug",
    "enhancement",
    "documentation",
    "question",
    "help wanted",
    "ios",
    "android",
    "wontfix",
    "dependencies",
]

PRIORITY_LABELS = {
    "high": "high priority",
    "medium": "medium priority",
    "low": "low priority",
}


def fingerprint(path: str, body: str, line: Optional[int] = None) -> str:
    raw = f"{path}:{line}:{body[:120]}" if line is not None else f"{path}:{body[:120]}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_env_optional(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def parse_repo(repo: str) -> Tuple[str, str]:
    if not repo:
        return "", ""
    parts = repo.split("/")
    if len(parts) != 2:
        return "", ""
    return parts[0], parts[1]


def build_model_list(primary: str, fallback_env: str = "", provider: str = "gemini") -> List[str]:
    fallback = [m.strip() for m in fallback_env.split(",") if m.strip()]
    if provider == "ollama":
        base_fallbacks = OLLAMA_FALLBACK_MODELS
    elif provider in ("openai", "openai-compatible", "deepseek"):
        base_fallbacks = OPENAI_FALLBACK_MODELS
    else:
        base_fallbacks = FALLBACK_MODELS

    models = [primary] + fallback + base_fallbacks
    seen = set()
    return [m for m in models if not (m in seen or seen.add(m))]


def load_repo_config(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    base = root_dir or Path.cwd()
    candidate_paths = [
        base / ".github" / "poing.json",
        base / "poing.json",
        base / ".poing.json",
    ]
    for path in candidate_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load config file at {path}: {e}", file=sys.stderr)
    return {}


class Config:
    def __init__(
        self,
        mode: Optional[str] = None,
        provider: Optional[str] = None,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        deepseek_api_key: Optional[str] = None,
        github_token: Optional[str] = None,
        repo: Optional[str] = None,
        pr_number: Optional[str] = None,
        base_ref: Optional[str] = None,
        pr_title: Optional[str] = None,
        head_sha: Optional[str] = None,
        issue_number: Optional[str] = None,
        issue_title: Optional[str] = None,
        issue_body: Optional[str] = None,
        issue_action: Optional[str] = None,
        model_name: Optional[str] = None,
        max_chars: Optional[int] = None,
        max_batches: Optional[int] = None,
        local: bool = False,
        dry_run: bool = False,
        staged: bool = False,
        diff_target: Optional[str] = None,
        files: Optional[List[str]] = None,
        output_format: Optional[str] = None,
        fail_on_changes: bool = False,
        config_data: Optional[Dict[str, Any]] = None,
    ):
        file_config = config_data if config_data is not None else load_repo_config()
        self.file_config = file_config

        self.MODE = (
            mode or get_env_optional("MODE") or "review"
        ).lower()

        self.LOCAL = local or (get_env_optional("LOCAL", "false").lower() == "true")
        self.DRY_RUN = dry_run or (get_env_optional("DRY_RUN", "false").lower() == "true")
        self.STAGED = staged or (get_env_optional("STAGED", "false").lower() == "true")
        self.DIFF_TARGET = diff_target or get_env_optional("DIFF_TARGET") or None
        self.FILES = files or ([f.strip() for f in get_env_optional("FILES").split(",") if f.strip()] if get_env_optional("FILES") else None)
        self.OUTPUT_FORMAT = output_format or get_env_optional("OUTPUT_FORMAT", "terminal").lower()
        self.FAIL_ON_CHANGES = fail_on_changes or (get_env_optional("FAIL_ON_CHANGES", "false").lower() == "true")

        section_key = "review"
        if self.MODE == "triage":
            section_key = "triage"
        elif self.MODE in ("sync", "dependencies"):
            section_key = "dependencies"

        section_cfg = file_config.get(section_key, {})

        # Provider configuration
        configured_provider = section_cfg.get("provider") or file_config.get("provider")
        self.PROVIDER = (
            provider
            or get_env_optional("AI_PROVIDER")
            or get_env_optional("PROVIDER")
            or configured_provider
            or "auto"
        ).lower()

        # API Base & Keys
        configured_api_base = section_cfg.get("api_base") or file_config.get("api_base")
        self.API_BASE = (
            api_base
            or get_env_optional("AI_BASE_URL")
            or get_env_optional("API_BASE")
            or get_env_optional("OLLAMA_HOST")
            or get_env_optional("OLLAMA_BASE_URL")
            or get_env_optional("OPENAI_BASE_URL")
            or configured_api_base
        )

        self.GEMINI_API_KEY = (
            gemini_api_key or get_env_optional("GEMINI_API_KEY")
        )
        self.OPENAI_API_KEY = (
            openai_api_key or get_env_optional("OPENAI_API_KEY")
        )
        self.DEEPSEEK_API_KEY = (
            deepseek_api_key or get_env_optional("DEEPSEEK_API_KEY")
        )
        self.API_KEY = (
            api_key
            or get_env_optional("AI_API_KEY")
            or get_env_optional("API_KEY")
            or self.GEMINI_API_KEY
            or self.OPENAI_API_KEY
            or self.DEEPSEEK_API_KEY
        )

        self.GITHUB_TOKEN = github_token or get_env_optional("GITHUB_TOKEN") or get_env_optional("GH_TOKEN")
        self.REPO = repo or get_env_optional("REPO") or get_env_optional("GITHUB_REPOSITORY")
        self.owner, self.repo_name = parse_repo(self.REPO)

        self.PR_NUMBER = pr_number or get_env_optional("PR_NUMBER")
        self.BASE_REF = base_ref or get_env_optional("BASE_REF", "master")
        self.PR_TITLE = pr_title or get_env_optional("PR_TITLE")
        self.HEAD_SHA = head_sha or get_env_optional("PR_HEAD_SHA") or get_env_optional("GITHUB_SHA")

        self.ISSUE_NUMBER = issue_number or get_env_optional("ISSUE_NUMBER")
        self.ISSUE_TITLE = issue_title or get_env_optional("ISSUE_TITLE")
        self.ISSUE_BODY = issue_body or get_env_optional("ISSUE_BODY")
        self.ISSUE_ACTION = issue_action or get_env_optional("ISSUE_ACTION", "opened")
        self.COMMENT_BODY = get_env_optional("COMMENT_BODY")
        self.IS_MAINTAINER = get_env_optional("IS_MAINTAINER", "false").lower() == "true"
        self.BOT_LOGIN = get_env_optional("BOT_LOGIN")
        self.TRIGGER_ACTION = get_env_optional("TRIGGER_ACTION")

        # Determine default model
        configured_model = section_cfg.get("model")
        if self.PROVIDER == "ollama":
            default_model = configured_model if configured_provider == "ollama" else None
        elif self.PROVIDER in ("openai", "openai-compatible"):
            default_model = configured_model if configured_provider in ("openai", "openai-compatible") else "gpt-4o-mini"
        elif self.PROVIDER == "deepseek":
            default_model = configured_model if configured_provider == "deepseek" else "deepseek-chat"
        else:
            default_model = configured_model or "gemini-3.7-flash"

        self.PRIMARY_MODEL = model_name or get_env_optional("MODEL_NAME") or default_model
        fallback_str = ",".join(section_cfg.get("fallback_models", [])) if (configured_provider == self.PROVIDER or self.PROVIDER == "gemini") else ""
        if self.PRIMARY_MODEL:
            self.MODELS_TO_TRY = build_model_list(
                self.PRIMARY_MODEL,
                get_env_optional("FALLBACK_MODELS", fallback_str),
                provider=self.PROVIDER,
            )
        else:
            self.MODELS_TO_TRY = []

        default_max_chars = section_cfg.get("max_chars", 100000)
        self.MAX_CHARS = max_chars or int(get_env_optional("MAX_CHARS", str(default_max_chars)))
        self.MAX_BATCHES = max_batches or int(get_env_optional("MAX_BATCHES", str(section_cfg.get("max_batches", 5))))
        self.STRICT_GROUND_TRUTH = section_cfg.get("strict_ground_truth", True)
