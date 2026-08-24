import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from poing_reviewer.parsers.gdscript_config import GDScriptConfigParser
from poing_reviewer.parsers.gradle import GradleParser
from poing_reviewer.parsers.swift_package import SwiftPackageParser


class TestParsers(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_gdscript_config_parser(self):
        gd_file = self.test_dir / "config.gd"
        gd_file.write_text(
            'const ANDROID_DEP := "com.google.android.gms:play-services-ads:22.0.0"\n'
            'const IOS_DEP := {"url": "https://github.com/googleads/swift-package-manager-google-mobile-ads.git", "version": "10.0.0"}\n',
            encoding="utf-8"
        )

        mock_maven = MagicMock()
        mock_maven.get_latest_version.return_value = "23.0.0"
        mock_spm = MagicMock()
        mock_spm.get_latest_version.return_value = "11.0.0"

        parser = GDScriptConfigParser(
            maven_datasource=mock_maven,
            spm_datasource=mock_spm,
            root_dir=self.test_dir,
        )

        updates = parser.sync_file(gd_file, dry_run=False)
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0].new_version, "23.0.0")
        self.assertEqual(updates[1].new_version, "11.0.0")

        updated_content = gd_file.read_text(encoding="utf-8")
        self.assertIn("23.0.0", updated_content)
        self.assertIn("11.0.0", updated_content)

    def test_gradle_parser(self):
        gradle_file = self.test_dir / "build.gradle"
        gradle_file.write_text(
            'dependencies {\n'
            '    implementation "com.google.android.gms:play-services-ads:22.0.0"\n'
            '}\n',
            encoding="utf-8"
        )

        mock_maven = MagicMock()
        mock_maven.get_latest_version.return_value = "23.0.0"

        parser = GradleParser(maven_datasource=mock_maven, root_dir=self.test_dir)
        updates = parser.sync_file(gradle_file, dry_run=False)
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].new_version, "23.0.0")

        updated_content = gradle_file.read_text(encoding="utf-8")
        self.assertIn("23.0.0", updated_content)


if __name__ == "__main__":
    unittest.main()
