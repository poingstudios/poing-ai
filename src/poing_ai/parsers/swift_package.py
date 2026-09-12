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
from typing import Any, Dict, List, Optional, Set

from poing_ai.core.logging import get_logger
from poing_ai.core.models import DependencyUpdate
from poing_ai.datasources.spm_github import SPMGitHubDatasource
from poing_ai.parsers.base import BaseParser, classify_version_update

logger = get_logger("parsers.swift_package")


class SwiftPackageParser(BaseParser):
    SPM_DEP_PATTERN = re.compile(
        r'(\.package\s*\(\s*url:\s*"https://github\.com/([^/]+/[^/.]+?)(?:\.git)?"\s*,\s*(?:exact|from):\s*")([^"]+)("\s*\))'
    )

    def __init__(
        self,
        spm_datasource: Optional[SPMGitHubDatasource] = None,
        root_dir: Optional[Path] = None,
        config: Optional[Any] = None,
        ignore_versions: Optional[Dict[str, set]] = None,
        pinned_versions: Optional[Dict[str, str]] = None,
    ):
        self.spm = spm_datasource or SPMGitHubDatasource()
        self.root_dir = root_dir or Path.cwd()
        self.config = config

        self._ignore_versions: Dict[str, set] = ignore_versions or (config.DEPENDENCY_IGNORE if config else {})
        self._pinned_versions: Dict[str, str] = pinned_versions or (config.DEPENDENCY_PINNED if config else {})

    @property
    def target_type(self) -> str:
        return "swift_package"

    def _get_ignored_versions(self, dependency: str) -> set:
        clean_dep = dependency.replace("https://github.com/", "").rstrip(".git").strip("/")
        return self._ignore_versions.get(clean_dep, set())

    def _get_pinned_version(self, dependency: str) -> Optional[str]:
        clean_dep = dependency.replace("https://github.com/", "").rstrip(".git").strip("/")
        return self._pinned_versions.get(clean_dep)

    def sync_file(self, file_path: Path, dry_run: bool = False) -> List[DependencyUpdate]:
        if not file_path.exists():
            return []
        content = file_path.read_text(encoding="utf-8")
        updates: List[DependencyUpdate] = []
        modified = False

        rel_path = str(file_path.relative_to(self.root_dir) if file_path.is_relative_to(self.root_dir) else file_path)

        def _replace_spm_dep(match: re.Match) -> str:
            nonlocal modified
            prefix = match.group(1)
            repo_path = match.group(2)
            current_ver = match.group(3)
            suffix = match.group(4)

            pinned_ver = self._get_pinned_version(repo_path)
            if pinned_ver:
                target_ver = pinned_ver
            else:
                ignored = self._get_ignored_versions(repo_path)
                target_ver = self.spm.get_latest_version(repo_path, ignored_versions=ignored)

            if target_ver and target_ver != current_ver:
                logger.info(f"[Package.swift] {repo_path}: {current_ver} -> {target_ver}")
                updates.append(
                    DependencyUpdate(
                        platform="iOS SPM",
                        dependency=repo_path,
                        old_version=current_ver,
                        new_version=target_ver,
                        file_path=rel_path,
                        update_type=classify_version_update(current_ver, target_ver),
                    )
                )
                modified = True
                return f"{prefix}{target_ver}{suffix}"
            return match.group(0)

        new_content = self.SPM_DEP_PATTERN.sub(_replace_spm_dep, content)

        if modified and not dry_run:
            file_path.write_text(new_content, encoding="utf-8")

        return updates

