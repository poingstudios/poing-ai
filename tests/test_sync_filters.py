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

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from poing_ai.core.config import Config
from poing_ai.datasources.maven import MavenDatasource
from poing_ai.datasources.spm_github import SPMGitHubDatasource
from poing_ai.parsers.gdscript_config import GDScriptConfigParser
from poing_ai.parsers.gradle import GradleParser
from poing_ai.parsers.swift_package import SwiftPackageParser


class TestSyncFilters(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_config_dependency_policies(self):
        config_data = {
            "dependencies": {
                "ignore": {
                    "googleads/googleads-mobile-ios-mediation-maio": ["2.2.200", "v2.2.300"],
                    "https://github.com/some/repo.git": "1.0.0",
                },
                "pinned": {
                    "com.google.ads.mediation:vungle": "v7.7.7.0",
                    "https://github.com/googleads/swift-package-manager-google-mobile-ads.git": "13.8.0",
                },
                "include_groups": [
                    "com.google.android.libraries.ads",
                    "com.google.ads.mediation",
                ],
            }
        }
        cfg = Config(config_data=config_data, local=True)

        # Verify ignore
        self.assertTrue(cfg.is_version_ignored("googleads/googleads-mobile-ios-mediation-maio", "2.2.300"))
        self.assertTrue(cfg.is_version_ignored("googleads/googleads-mobile-ios-mediation-maio", "v2.2.200"))
        self.assertFalse(cfg.is_version_ignored("googleads/googleads-mobile-ios-mediation-maio", "2.2.3"))
        self.assertTrue(cfg.is_version_ignored("some/repo", "1.0.0"))

        # Verify pinned
        self.assertEqual(cfg.get_pinned_version("com.google.ads.mediation:vungle"), "7.7.7.0")
        self.assertEqual(
            cfg.get_pinned_version("googleads/swift-package-manager-google-mobile-ads"), "13.8.0"
        )
        self.assertIsNone(cfg.get_pinned_version("other/lib"))

        # Verify group allowed
        self.assertTrue(cfg.is_group_allowed("com.google.ads.mediation:unity:4.20.0"))
        self.assertTrue(cfg.is_group_allowed("com.google.android.libraries.ads.mobile.sdk:admob:23.0.0"))
        self.assertFalse(cfg.is_group_allowed("androidx.constraintlayout:constraintlayout:2.2.0"))

    def test_spm_datasource_with_ignored_versions(self):
        ds = SPMGitHubDatasource()
        ds._fetch_latest_release = MagicMock(return_value="2.2.300")
        ds._fetch_first_tag = MagicMock(return_value="2.2.3")

        # Without ignore, latest release is returned
        ver = ds.get_latest_version("googleads/googleads-mobile-ios-mediation-maio")
        self.assertEqual(ver, "2.2.300")

        # With ignore, falls back to first non-ignored tag
        ver_ignored = ds.get_latest_version(
            "googleads/googleads-mobile-ios-mediation-maio", ignored_versions={"2.2.300"}
        )
        self.assertEqual(ver_ignored, "2.2.3")
        ds._fetch_first_tag.assert_called_with(
            "googleads/googleads-mobile-ios-mediation-maio", ignored={"2.2.300"}
        )

    def test_gdscript_config_parser_ignore_and_pin(self):
        gd_file = self.test_dir / "poing_godot_admob_maio.gd"
        gd_file.write_text(
            'extends EditorExportPlugin\n'
            'const PLUGIN_NAME := "maio"\n'
            'var _dependency_library := ["com.google.ads.mediation:maio:2.0.9.0"]\n'
            'func get_spm_packages() -> Array[Dictionary]:\n'
            '\treturn [\n'
            '\t\t{\n'
            '\t\t\t"url": "https://github.com/googleads/googleads-mobile-ios-mediation-maio.git",\n'
            '\t\t\t"version": "2.2.3",\n'
            '\t\t\t"products": ["MaioAdapterTarget"]\n'
            '\t\t}\n'
            '\t]\n',
            encoding="utf-8",
        )

        mock_maven = MagicMock()
        mock_maven.get_latest_version.return_value = "2.0.9.1"
        mock_spm = MagicMock()
        # Simulate SPM datasource respecting ignored versions: when 2.2.300 is ignored, it returns None or 2.2.3
        mock_spm.get_latest_version.return_value = "2.2.3"

        config_data = {
            "dependencies": {
                "ignore": {
                    "googleads/googleads-mobile-ios-mediation-maio": ["2.2.300"],
                },
                "pinned": {
                    "com.google.ads.mediation:maio": "2.0.9.0",
                },
            }
        }
        cfg = Config(config_data=config_data, local=True)

        parser = GDScriptConfigParser(
            maven_datasource=mock_maven,
            spm_datasource=mock_spm,
            root_dir=self.test_dir,
            config=cfg,
        )

        updates = parser.sync_file(gd_file, dry_run=False)
        # Both Maio Android and iOS remain unchanged because Android is pinned to 2.0.9.0 and iOS ignores 2.2.300
        self.assertEqual(len(updates), 0)
        content = gd_file.read_text(encoding="utf-8")
        self.assertIn('"2.2.3"', content)
        self.assertIn('"com.google.ads.mediation:maio:2.0.9.0"', content)

    def test_gdscript_config_parser_group_filtering(self):
        gd_file = self.test_dir / "poing_godot_admob_applovin.gd"
        gd_file.write_text(
            'var _dep1 := ["com.google.ads.mediation:applovin:13.6.3.0"]\n'
            'var _dep2 := ["androidx.constraintlayout:constraintlayout:2.2.0"]\n',
            encoding="utf-8",
        )

        mock_maven = MagicMock()
        mock_maven.get_latest_version.side_effect = lambda coord, ignored_versions=None: {
            "com.google.ads.mediation:applovin": "13.6.4.0",
            "androidx.constraintlayout:constraintlayout": "2.2.2",
        }.get(coord)

        config_data = {
            "dependencies": {
                "include_groups": ["com.google.ads.mediation"],
            }
        }
        cfg = Config(config_data=config_data, local=True)

        parser = GDScriptConfigParser(
            maven_datasource=mock_maven,
            root_dir=self.test_dir,
            config=cfg,
        )

        updates = parser.sync_file(gd_file, dry_run=False)
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].dependency, "com.google.ads.mediation:applovin")
        self.assertEqual(updates[0].new_version, "13.6.4.0")

        content = gd_file.read_text(encoding="utf-8")
        self.assertIn('"com.google.ads.mediation:applovin:13.6.4.0"', content)
        # androidx.constraintlayout remains untouched
        self.assertIn('"androidx.constraintlayout:constraintlayout:2.2.0"', content)


if __name__ == "__main__":
    unittest.main()
