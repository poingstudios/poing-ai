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
from typing import Optional


class BaseDatasource(ABC):
    """Abstract base class for upstream package/dependency version fetchers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the datasource."""
        pass

    @abstractmethod
    def get_latest_version(self, identifier: str) -> Optional[str]:
        """Fetch the latest stable version for the given dependency identifier."""
        pass
