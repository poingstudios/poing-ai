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
from poing_reviewer.datasources.upm_registry import UPMRegistryDatasource
from poing_reviewer.parsers.base import BaseParser, classify_version_update

logger = get_logger("parsers.unity_package")


class UnityPackageParser(BaseParser):
    def __init__(
        self,
        upm_datasource: Optional[UPMRegistryDatasource] = None,
        root_dir: Optional[Path] = None,
    ):
        self.upm = upm_datasource or UPMRegistryDatasource()
        self.root_dir = root_dir or Path.cwd()

    @property
    def target_type(self) -> str:
        return "unity_package"

    def sync_file(self, file_path: Path, dry_run: bool = False) -> List[DependencyUpdate]:
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read Unity package file {file_path}: {e}")
            return []

        deps = data.get("dependencies", {})
        if not deps:
            return []

        updates: List[DependencyUpdate] = []
        modified = False
        rel_path = str(file_path.relative_to(self.root_dir) if file_path.is_relative_to(self.root_dir) else file_path)

        for pkg_name, current_ver in list(deps.items()):
            # Only check registry packages (e.g. com.unity.xxx or com.company.xxx with semver version)
            if not isinstance(current_ver, str) or current_ver.startswith("file:") or current_ver.startswith("git"):
                continue

            latest_ver = self.upm.get_latest_version(pkg_name)
            if latest_ver and latest_ver != current_ver:
                logger.info(f"[Unity UPM] {pkg_name}: {current_ver} -> {latest_ver}")
                updates.append(
                    DependencyUpdate(
                        platform="Unity UPM",
                        dependency=pkg_name,
                        old_version=current_ver,
                        new_version=latest_ver,
                        file_path=rel_path,
                        update_type=classify_version_update(current_ver, latest_ver),
                    )
                )
                deps[pkg_name] = latest_ver
                modified = True

        if modified and not dry_run:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")

        return updates
