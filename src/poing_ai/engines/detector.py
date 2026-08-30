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
from typing import Optional

from poing_ai.engines.base import BaseEngineAnalyzer
from poing_ai.engines.generic import GenericAnalyzer
from poing_ai.engines.godot import GodotAnalyzer
from poing_ai.engines.unity import UnityAnalyzer
from poing_ai.engines.unreal import UnrealAnalyzer


def detect_engine(root_dir: Optional[Path] = None, explicit_engine: Optional[str] = None) -> BaseEngineAnalyzer:
    if explicit_engine:
        lower = explicit_engine.lower()
        if "godot" in lower:
            return GodotAnalyzer()
        if "unity" in lower:
            return UnityAnalyzer()
        if "unreal" in lower:
            return UnrealAnalyzer()
        return GenericAnalyzer()

    base = root_dir or Path.cwd()

    # 1. Godot Check
    if (base / "project.godot").exists() or any(base.glob("**/project.godot")) or any(base.glob("**/*.gd")):
        return GodotAnalyzer()

    # 2. Unity Check
    if (base / "ProjectSettings" / "ProjectSettings.asset").exists() or (base / "Packages" / "manifest.json").exists():
        return UnityAnalyzer()

    # 3. Unreal Check
    if any(base.glob("*.uproject")) or any(base.glob("**/*.uplugin")):
        return UnrealAnalyzer()

    return GenericAnalyzer()
