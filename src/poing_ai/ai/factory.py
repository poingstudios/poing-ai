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

from typing import Optional

from poing_ai.ai.base import BaseAIProvider
from poing_ai.ai.gemini import GeminiProvider
from poing_ai.ai.ollama import OllamaProvider
from poing_ai.ai.openai_compatible import OpenAICompatibleProvider
from poing_ai.core.config import Config
from poing_ai.core.logging import get_logger

logger = get_logger("ai.factory")


def create_ai_provider(config: Config) -> BaseAIProvider:
    """Instantiates the appropriate AI provider based on configuration and environment."""
    provider_name = (config.PROVIDER or "").lower().strip()

    if provider_name == "ollama":
        base_url = config.API_BASE or "http://localhost:11434"
        logger.info(f"Using Ollama provider at {base_url}")
        models_to_try = [config.PRIMARY_MODEL] if config.PRIMARY_MODEL and not config.PRIMARY_MODEL.startswith("gemini-") else None
        return OllamaProvider(
            base_url=base_url,
            models_to_try=models_to_try,
        )

    if provider_name in ("openai", "openai-compatible", "deepseek", "groq", "openrouter"):
        api_key = config.API_KEY or config.OPENAI_API_KEY or config.DEEPSEEK_API_KEY or ""
        base_url = config.API_BASE
        if not base_url and provider_name == "deepseek":
            base_url = "https://api.deepseek.com/v1"
        elif not base_url and provider_name == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif not base_url and provider_name == "openrouter":
            base_url = "https://openrouter.ai/api/v1"

        logger.info(f"Using OpenAI-compatible provider (base_url={base_url or 'https://api.openai.com/v1'})")
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            models_to_try=config.MODELS_TO_TRY,
        )

    if provider_name == "gemini":
        logger.info("Using Google Gemini provider")
        api_key = config.GEMINI_API_KEY or config.API_KEY or ""
        return GeminiProvider(
            api_key=api_key,
            models_to_try=config.MODELS_TO_TRY,
        )

    # Auto-detection logic when provider_name is empty or 'auto'
    if config.GEMINI_API_KEY:
        logger.info("Auto-detected Gemini provider (GEMINI_API_KEY found)")
        return GeminiProvider(
            api_key=config.GEMINI_API_KEY,
            models_to_try=config.MODELS_TO_TRY,
        )

    if config.OPENAI_API_KEY or config.DEEPSEEK_API_KEY:
        base_url = config.API_BASE or ("https://api.deepseek.com/v1" if config.DEEPSEEK_API_KEY else None)
        api_key = config.DEEPSEEK_API_KEY or config.OPENAI_API_KEY or ""
        logger.info(f"Auto-detected OpenAI-compatible provider (base_url={base_url})")
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            models_to_try=config.MODELS_TO_TRY,
        )

    if config.API_BASE:
        if "11434" in config.API_BASE or "ollama" in config.API_BASE.lower():
            logger.info(f"Auto-detected Ollama provider at {config.API_BASE}")
            return OllamaProvider(
                base_url=config.API_BASE,
                models_to_try=config.MODELS_TO_TRY,
            )
        logger.info(f"Auto-detected OpenAI-compatible endpoint at {config.API_BASE}")
        return OpenAICompatibleProvider(
            api_key=config.API_KEY or "dummy",
            base_url=config.API_BASE,
            models_to_try=config.MODELS_TO_TRY,
        )

    if config.LOCAL:
        logger.info("Local mode without cloud API keys: Defaulting to local Ollama provider")
        models_to_try = [config.PRIMARY_MODEL] if config.PRIMARY_MODEL and not config.PRIMARY_MODEL.startswith("gemini-") else None
        return OllamaProvider(
            base_url="http://localhost:11434",
            models_to_try=models_to_try,
        )

    # Fallback to Gemini
    return GeminiProvider(
        api_key=config.GEMINI_API_KEY,
        models_to_try=config.MODELS_TO_TRY,
    )
