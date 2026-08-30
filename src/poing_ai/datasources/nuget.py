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
from typing import Optional

from poing_ai.core.logging import get_logger
from poing_ai.datasources.base import BaseDatasource

logger = get_logger("datasources.nuget")


class NuGetDatasource(BaseDatasource):
    USER_AGENT = "PoingReviewer-NuGetSync/1.0"
    API_URL = "https://api.nuget.org/v3-flatcontainer/{package_id}/index.json"

    @property
    def name(self) -> str:
        return "NuGet"

    def get_latest_version(self, package_id: str) -> Optional[str]:
        url = self.API_URL.format(package_id=package_id.lower())
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    versions = data.get("versions", [])
                    if versions:
                        # Return latest stable version (excluding pre-releases if possible)
                        stables = [v for v in versions if "-" not in v]
                        return stables[-1] if stables else versions[-1]
        except Exception:
            pass
        return None
