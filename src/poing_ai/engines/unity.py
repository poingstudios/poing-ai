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

from typing import List
from poing_ai.engines.base import BaseEngineAnalyzer


class UnityAnalyzer(BaseEngineAnalyzer):
    @property
    def name(self) -> str:
        return "Unity Engine"

    def get_file_patterns(self) -> List[str]:
        return ["ProjectSettings/ProjectSettings.asset", "Packages/manifest.json", "*.asmdef", "*.unity", "*.prefab"]

    def get_review_guidelines(self) -> str:
        return """### Unity Engine Specific Guidelines
- **Performance in Hot Loops**: Avoid GC allocations (boxing, LINQ, `new`, string formatting) inside `Update()`, `FixedUpdate()`, or `LateUpdate()`.
- **Serialization**: Use `[SerializeField] private` instead of public fields when exposing variables to the Inspector.
- **Null Checks**: Remember that Unity's `UnityEngine.Object` overrides `== null` (fake null); avoid using null-conditional operators (`?.` or `??`) on `UnityEngine.Object` derived types.
- **Coroutines & Async**: Ensure `CancellationToken` or coroutine stopping on `OnDestroy()` to avoid memory leaks.
- **UPM Standards**: Ensure `package.json` adheres to Semantic Versioning and dependencies are properly specified in `dependencies` block."""
