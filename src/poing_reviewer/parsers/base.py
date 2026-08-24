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
from pathlib import Path
from typing import List

from poing_reviewer.core.models import DependencyUpdate


def classify_version_update(old_ver: str, new_ver: str) -> str:
    """Classifies version update as MAJOR, MINOR, or PATCH."""
    old_parts = old_ver.split(".")
    new_parts = new_ver.split(".")
    try:
        if old_parts[0] != new_parts[0]:
            return "MAJOR"
        if len(old_parts) > 1 and len(new_parts) > 1 and old_parts[1] != new_parts[1]:
            return "MINOR"
        return "PATCH"
    except Exception:
        return "MINOR"


class BaseParser(ABC):
    """Abstract base class for dependency file parsers and updaters."""

    @property
    @abstractmethod
    def target_type(self) -> str:
        """Type identifier for the target configuration (e.g., 'gradle', 'gdscript_config')."""
        pass

    @abstractmethod
    def sync_file(self, file_path: Path, dry_run: bool = False) -> List[DependencyUpdate]:
        """Parses the file, queries datasources for updates, modifies file if not dry_run, returns updates."""
        pass
