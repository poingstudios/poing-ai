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

from pathlib import Path
import re
from typing import List, Optional

from poing_reviewer.core.logging import get_logger
from poing_reviewer.core.models import DependencyUpdate
from poing_reviewer.datasources.maven import MavenDatasource
from poing_reviewer.parsers.base import BaseParser, classify_version_update

logger = get_logger("parsers.gradle")


class GradleParser(BaseParser):
    GRADLE_DEP_PATTERN = re.compile(
        r'((?:implementation|api|compileOnly|runtimeOnly|testImplementation)\s*\(?[\'"])([a-zA-Z0-9._-]+:[a-zA-Z0-9._-]+):([a-zA-Z0-9._+-]+)([\'"]\)?)'
    )

    def __init__(
        self,
        maven_datasource: Optional[MavenDatasource] = None,
        root_dir: Optional[Path] = None,
    ):
        self.maven = maven_datasource or MavenDatasource()
        self.root_dir = root_dir or Path.cwd()

    @property
    def target_type(self) -> str:
        return "gradle"

    def sync_file(self, file_path: Path, dry_run: bool = False) -> List[DependencyUpdate]:
        if not file_path.exists():
            return []
        content = file_path.read_text(encoding="utf-8")
        updates: List[DependencyUpdate] = []
        modified = False

        rel_path = str(file_path.relative_to(self.root_dir) if file_path.is_relative_to(self.root_dir) else file_path)

        def _replace_gradle_dep(match: re.Match) -> str:
            nonlocal modified
            prefix = match.group(1)
            coord = match.group(2)
            current_ver = match.group(3)
            suffix = match.group(4)

            latest_ver = self.maven.get_latest_version(coord)
            if latest_ver and latest_ver != current_ver:
                logger.info(f"[Gradle] {coord}: {current_ver} -> {latest_ver}")
                updates.append(
                    DependencyUpdate(
                        platform="Gradle",
                        dependency=coord,
                        old_version=current_ver,
                        new_version=latest_ver,
                        file_path=rel_path,
                        update_type=classify_version_update(current_ver, latest_ver),
                    )
                )
                modified = True
                return f"{prefix}{coord}:{latest_ver}{suffix}"
            return match.group(0)

        new_content = self.GRADLE_DEP_PATTERN.sub(_replace_gradle_dep, content)

        if modified and not dry_run:
            file_path.write_text(new_content, encoding="utf-8")

        return updates
