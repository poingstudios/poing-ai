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

import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Optional

from poing_ai.core.logging import get_logger
from poing_ai.datasources.base import BaseDatasource

logger = get_logger("datasources.maven")


class MavenDatasource(BaseDatasource):
    USER_AGENT = "PoingReviewer-DependencySync/1.0"
    REPOSITORIES = [
        "https://dl.google.com/android/maven2",
        "https://repo1.maven.org/maven2",
    ]

    @property
    def name(self) -> str:
        return "Maven"

    def get_latest_version(self, coordinate: str) -> Optional[str]:
        if ":" not in coordinate:
            return None
        group_id, artifact_id = coordinate.split(":", 1)

        for repo_base in self.REPOSITORIES:
            version = self._fetch_version_from_repo(repo_base, group_id, artifact_id)
            if version:
                return version
        return None

    def _fetch_version_from_repo(self, repo_base: str, group_id: str, artifact_id: str) -> Optional[str]:
        group_path = group_id.replace(".", "/")
        url = f"{repo_base}/{group_path}/{artifact_id}/maven-metadata.xml"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    root = ET.fromstring(resp.read())
                    return root.findtext("./versioning/release") or root.findtext("./versioning/latest")
        except Exception:
            pass
        return None
