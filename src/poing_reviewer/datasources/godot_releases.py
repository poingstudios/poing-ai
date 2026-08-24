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
from typing import Dict, List, Optional

from poing_reviewer.core.logging import get_logger
from poing_reviewer.datasources.base import BaseDatasource

logger = get_logger("datasources.godot_releases")


class GodotReleasesDatasource(BaseDatasource):
    USER_AGENT = "PoingReviewer-GodotSync/1.0"

    def __init__(self, token: str = ""):
        self._token = token

    @property
    def name(self) -> str:
        return "Godot Engine Releases"

    def _get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": self.USER_AGENT}
        if self._token:
            headers["Authorization"] = f"token {self._token}"
        return headers

    def get_latest_version(self, channel: str = "stable") -> Optional[str]:
        releases = self.get_recent_releases()
        for tag in releases:
            clean_tag = tag.lstrip("v")
            if channel == "stable" and "stable" in clean_tag:
                return clean_tag.split("-")[0]
            if channel in clean_tag:
                return clean_tag
        return releases[0] if releases else None

    def get_recent_releases(self) -> List[str]:
        url = "https://api.github.com/repos/godotengine/godot/releases?per_page=15"
        try:
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    return [r.get("tag_name", "").lstrip("v") for r in data if "tag_name" in r]
        except Exception as e:
            logger.warning(f"Failed to fetch Godot releases: {e}")
        return []
