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
from typing import List


class BaseEngineAnalyzer(ABC):
    """Abstract interface for engine-specific rules and guidelines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the engine or ecosystem."""
        pass

    @abstractmethod
    def get_review_guidelines(self) -> str:
        """Returns engine-specific guidelines to inject into code review prompt."""
        pass

    @abstractmethod
    def get_file_patterns(self) -> List[str]:
        """Glob patterns identifying this engine/ecosystem."""
        pass
