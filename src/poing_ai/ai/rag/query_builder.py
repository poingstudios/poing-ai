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
from typing import Iterable, Set


EXTENSION_TAG_MAP = {
    ".gd": {"gdscript", "godot", "typing", "syntax"},
    ".cs": {"csharp", "dotnet", "mono", "parity"},
    ".kt": {"kotlin", "android", "gradle", "jni"},
    ".java": {"java", "android"},
    ".swift": {"swift", "ios", "spm", "podspec"},
    ".py": {"python", "standards"},
    ".cpp": {"cpp", "c++", "gdextension", "memory"},
    ".h": {"cpp", "header", "gdextension"},
    ".hpp": {"cpp", "header", "gdextension"},
    ".rs": {"rust"},
    ".ts": {"typescript"},
    ".js": {"javascript"},
    ".yml": {"github-actions", "workflow", "ci"},
    ".yaml": {"github-actions", "workflow", "ci"},
}

PATH_KEYWORD_MAP = {
    "internal": {"internal", "encapsulation", "preload", "class_name"},
    "addons": {"addon", "plugin", "editor"},
    "platforms": {"platform", "cross-platform", "bridge"},
    "android": {"android", "gradle"},
    "ios": {"ios", "swift"},
    "csharp": {"csharp", "parity"},
    "workflows": {"github-actions", "actions"},
}


def build_diff_rag_query(file_paths: Iterable[str], diff_text: str = "") -> str:
    """Builds a targeted semantic RAG query based on modified files, languages, and patterns in the diff."""
    tags: Set[str] = {"guidelines", "coding standards", "architecture"}

    for fpath in file_paths:
        path_obj = Path(fpath)
        suffix = path_obj.suffix.lower()
        if suffix in EXTENSION_TAG_MAP:
            tags.update(EXTENSION_TAG_MAP[suffix])

        parts_lower = [p.lower() for p in path_obj.parts]
        for key, path_tags in PATH_KEYWORD_MAP.items():
            if key in parts_lower:
                tags.update(path_tags)

    # Check for specific critical keywords inside added lines
    diff_lower = diff_text.lower()
    if "class_name" in diff_lower:
        tags.add("class_name")
    if "preload(" in diff_lower:
        tags.add("preload")
    if ":=" in diff_lower or "var " in diff_lower:
        tags.add("type inference")
    if "singleton" in diff_lower or "engine.get_singleton" in diff_lower:
        tags.add("singleton bridge")

    return " ".join(sorted(tags))
