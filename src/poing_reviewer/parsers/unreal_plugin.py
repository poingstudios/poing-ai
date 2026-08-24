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
from pathlib import Path
from typing import Any, Dict, List, Optional

from poing_reviewer.core.logging import get_logger
from poing_reviewer.core.models import DependencyUpdate
from poing_reviewer.parsers.base import BaseParser

logger = get_logger("parsers.unreal_plugin")


class UnrealPluginParser(BaseParser):
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or Path.cwd()

    @property
    def target_type(self) -> str:
        return "unreal_plugin"

    def sync_file(self, file_path: Path, dry_run: bool = False) -> List[DependencyUpdate]:
        # Unreal plugin descriptor validation & inspection
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read Unreal descriptor {file_path}: {e}")
            return []

        # Unreal .uplugin / .uproject plugins list inspection
        plugins = data.get("Plugins", [])
        updates: List[DependencyUpdate] = []
        return updates
