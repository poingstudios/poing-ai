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
import urllib.request
from typing import Dict, Optional

from poing_ai.core.logging import get_logger
from poing_ai.datasources.base import BaseDatasource

logger = get_logger("datasources.spm_github")


class SPMGitHubDatasource(BaseDatasource):
    USER_AGENT = "PoingReviewer-DependencySync/1.0"

    def __init__(self, token: str = ""):
        self._token = token

    @property
    def name(self) -> str:
        return "SPM / GitHub"

    def _get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": self.USER_AGENT}
        if self._token:
            headers["Authorization"] = f"token {self._token}"
        return headers

    def get_latest_version(self, repo_path: str) -> Optional[str]:
        # Strip https://github.com/ and trailing .git if present
        clean_path = repo_path.replace("https://github.com/", "").rstrip(".git").strip("/")
        return self._fetch_latest_release(clean_path) or self._fetch_first_tag(clean_path)

    def _fetch_latest_release(self, repo_path: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{repo_path}/releases/latest"
        try:
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    return data.get("tag_name", "").lstrip("v")
        except Exception:
            pass
        return None

    def _fetch_first_tag(self, repo_path: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{repo_path}/tags?per_page=5"
        try:
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    tags = json.loads(resp.read().decode())
                    if tags:
                        return tags[0].get("name", "").lstrip("v")
        except Exception:
            pass
        return None
