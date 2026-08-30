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
import sys
from typing import Any, Dict, List, Optional

from poing_ai.ai.base import BaseAIProvider
from poing_ai.ai.factory import create_ai_provider
from poing_ai.ai.prompts.changelog import build_changelog_prompt
from poing_ai.core.config import Config
from poing_ai.core.logging import get_logger
from poing_ai.core.models import DependencyUpdate, SyncSummary
from poing_ai.parsers.base import BaseParser
from poing_ai.parsers.gdscript_config import GDScriptConfigParser
from poing_ai.parsers.gradle import GradleParser
from poing_ai.parsers.swift_package import SwiftPackageParser
from poing_ai.parsers.unity_package import UnityPackageParser
from poing_ai.parsers.unreal_plugin import UnrealPluginParser

logger = get_logger("services.sync")


class SyncService:
    def __init__(
        self,
        config: Config,
        ai_provider: Optional[BaseAIProvider] = None,
        root_dir: Optional[Path] = None,
    ):
        self.cfg = config
        self.root_dir = root_dir or Path.cwd()
        self.ai = ai_provider or create_ai_provider(config)

        self.parsers: Dict[str, BaseParser] = {
            "gdscript_config": GDScriptConfigParser(root_dir=self.root_dir),
            "gradle": GradleParser(root_dir=self.root_dir),
            "swift_package": SwiftPackageParser(root_dir=self.root_dir),
            "unity_package": UnityPackageParser(root_dir=self.root_dir),
            "unreal_plugin": UnrealPluginParser(root_dir=self.root_dir),
        }

    def _get_configured_targets(self) -> List[Dict[str, Any]]:
        deps_cfg = self.cfg.file_config.get("dependencies", {})
        targets = deps_cfg.get("targets", [])
        if targets:
            return targets

        # Default discovery fallback targets
        return [
            {
                "type": "gdscript_config",
                "paths": [
                    "platforms/android/src/**/config/*.gd",
                    "platforms/ios/src/**/config/*.gd",
                ],
            },
            {
                "type": "gradle",
                "paths": [
                    "platforms/android/build.gradle",
                    "build.gradle",
                ],
            },
            {
                "type": "swift_package",
                "paths": [
                    "platforms/ios/Package.swift",
                    "Package.swift",
                ],
            },
            {
                "type": "unity_package",
                "paths": [
                    "Packages/manifest.json",
                ],
            },
        ]

    def run(self) -> SyncSummary:
        logger.info(f"Starting dependency sync (dry_run={self.cfg.DRY_RUN})...")
        targets = self._get_configured_targets()
        all_updates: List[DependencyUpdate] = []

        for target in targets:
            target_type = target.get("type", "")
            parser = self.parsers.get(target_type)
            if not parser:
                logger.warning(f"No parser available for target type '{target_type}'. Skipping.")
                continue

            patterns = target.get("paths", [])
            matched_files: List[Path] = []
            for pattern in patterns:
                matched_files.extend(self.root_dir.glob(pattern))

            unique_files = sorted(list(set(matched_files)))
            for fpath in unique_files:
                if fpath.is_file():
                    updates = parser.sync_file(fpath, dry_run=self.cfg.DRY_RUN)
                    all_updates.extend(updates)

        if not all_updates:
            logger.info("All dependencies are already up-to-date.")
            return SyncSummary(has_updates=False)

        # Build Summary Table
        table_lines = [
            "| Platform | Dependency | Current Version | New Version | Update Type |",
            "|---|---|---|---|---|",
        ]
        for u in all_updates:
            table_lines.append(f"| {u.platform} | `{u.dependency}` | {u.old_version} | **{u.new_version}** | `{u.update_type}` |")
        summary_table = "\n".join(table_lines)

        # Generate AI Changelog Summary
        changelog_notes = ""
        try:
            prompt = build_changelog_prompt(all_updates)
            ai_summary = self.ai.generate_changelog_summary(prompt)
            if ai_summary:
                changelog_notes = ai_summary
        except Exception as e:
            logger.warning(f"Could not generate AI changelog summary: {e}")

        if not changelog_notes:
            changelog_notes = f"### Dependency Updates\n\n{summary_table}"

        summary = SyncSummary(
            has_updates=True,
            updates=all_updates,
            summary_table=summary_table,
            changelog_notes=changelog_notes,
        )

        if self.cfg.LOCAL:
            sys.stdout.write(
                f"\n{'=' * 60}\nDEPENDENCY SYNC SUMMARY\n{summary_table}\n\n--- AI RELEASE NOTES ---\n{changelog_notes}\n{'=' * 60}\n\n"
            )

        return summary
