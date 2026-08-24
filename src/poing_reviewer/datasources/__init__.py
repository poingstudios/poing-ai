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

from poing_reviewer.datasources.base import BaseDatasource
from poing_reviewer.datasources.godot_releases import GodotReleasesDatasource
from poing_reviewer.datasources.maven import MavenDatasource
from poing_reviewer.datasources.nuget import NuGetDatasource
from poing_reviewer.datasources.spm_github import SPMGitHubDatasource
from poing_reviewer.datasources.upm_registry import UPMRegistryDatasource

__all__ = [
    "BaseDatasource",
    "MavenDatasource",
    "SPMGitHubDatasource",
    "GodotReleasesDatasource",
    "UPMRegistryDatasource",
    "NuGetDatasource",
]
