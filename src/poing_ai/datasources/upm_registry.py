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

logger = get_logger("datasources.upm")


class UPMRegistryDatasource(BaseDatasource):
    USER_AGENT = "PoingReviewer-UPMSync/1.0"
    REGISTRIES = [
        "https://package.openupm.com",
        "https://packages.unity.com",
    ]

    @property
    def name(self) -> str:
        return "Unity Package Manager (UPM)"

    def get_latest_version(self, package_name: str) -> Optional[str]:
        for reg in self.REGISTRIES:
            url = f"{reg}/{package_name}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        dist_tags = data.get("dist-tags", {})
                        if "latest" in dist_tags:
                            return dist_tags["latest"]
            except Exception:
                pass
        return None
