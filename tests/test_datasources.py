import unittest
from unittest.mock import MagicMock, patch
from poing_reviewer.datasources.maven import MavenDatasource
from poing_reviewer.datasources.spm_github import SPMGitHubDatasource
from poing_reviewer.datasources.godot_releases import GodotReleasesDatasource
from poing_reviewer.datasources.nuget import NuGetDatasource


class TestDatasources(unittest.TestCase):
    def test_maven_datasource(self):
        datasource = MavenDatasource()
        xml_content = b"""<metadata>
            <versioning>
                <latest>23.0.0</latest>
                <release>23.0.0</release>
            </versioning>
        </metadata>"""

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = xml_content
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            version = datasource.get_latest_version("com.google.android.gms:play-services-ads")
            self.assertEqual(version, "23.0.0")

    def test_spm_github_datasource(self):
        datasource = SPMGitHubDatasource(token="fake_token")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"tag_name": "v11.2.0"}'
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            version = datasource.get_latest_version("googleads/swift-package-manager-google-mobile-ads")
            self.assertEqual(version, "11.2.0")


if __name__ == "__main__":
    unittest.main()
