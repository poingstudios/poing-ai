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


class UnrealAnalyzer(BaseEngineAnalyzer):
    @property
    def name(self) -> str:
        return "Unreal Engine"

    def get_file_patterns(self) -> List[str]:
        return ["*.uproject", "*.uplugin", "*.Build.cs", "*.Target.cs"]

    def get_review_guidelines(self) -> str:
        return """### Unreal Engine Specific Guidelines
- **Garbage Collection**: Raw pointer `UObject*` member variables must be marked with `UPROPERTY()` or wrapped with `TObjectPtr<T>` / `TWeakObjectPtr<T>` to prevent dangling pointers.
- **Unreal Containers**: Prefer `TArray`, `TMap`, `TSet`, and `FString`/`FName`/`FText` over STL standard library containers in gameplay code.
- **Memory & Delegates**: Use `CreateUObject` or `CreateWeakLambda` for delegates on `UObjects` to avoid crashes when referenced objects are destroyed.
- **Module Architecture**: Public headers should only expose what other modules need; keep internal implementation in private headers."""
