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

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from poing_ai.core.models import ReviewResult, TriageResult


class BaseAIProvider(ABC):
    """Abstract interface for AI model backends (Gemini, Local Ollama/vLLM, OpenAI, Claude)."""

    @abstractmethod
    def generate_review(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        """Generate structured code review."""
        pass

    @abstractmethod
    def generate_triage(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[TriageResult]:
        """Generate issue/PR triage categorization."""
        pass

    @abstractmethod
    def generate_changelog_summary(
        self,
        prompt: str,
        model_name: Optional[str] = None,
    ) -> Optional[str]:
        """Generate release notes & breaking changes summary."""
        pass
