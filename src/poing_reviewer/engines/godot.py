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
from poing_reviewer.engines.base import BaseEngineAnalyzer


class GodotAnalyzer(BaseEngineAnalyzer):
    @property
    def name(self) -> str:
        return "Godot Engine"

    def get_file_patterns(self) -> List[str]:
        return ["project.godot", "*.gd", "*.gdextension", "plugin.cfg", "*.tscn"]

    def get_review_guidelines(self) -> str:
        return """### Godot Engine Specific Guidelines
- **GDScript Type Inference**: Always use `:=` instead of `=` for typed variable initialization.
- **Internal Scripts**: Scripts under `addons/*/internal/` must NOT define a `class_name`; they must be loaded explicitly via `preload()`.
- **Signals**: Signal names should follow `snake_case` (e.g. `user_rewarded`), bridge callbacks prefixed with `_on_...`.
- **C# / GDScript Parity**: When modifying public API methods in plugins supporting C# and GDScript, ensure 1:1 API parity.
- **Node Lifecycle**: Properly clean up nodes using `queue_free()` and disconnect signals when appropriate.
- **GDExtension**: Verify memory management, `Ref<T>` vs raw pointers, and clean ClassDB registration."""
