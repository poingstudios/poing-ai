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

import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from poing_ai.core.logging import get_logger

logger = get_logger("ai.rag.symbol_impact")

IGNORED_DIRS = {
    ".git", ".github", ".venv", "venv", "node_modules",
    "build", "dist", ".pytest_cache", "__pycache__", "site"
}

IGNORED_SYMBOLS = {
    "__init__", "__str__", "__repr__", "__enter__", "__exit__",
    "_ready", "_process", "_physics_process", "_enter_tree", "_exit_tree",
    "main", "run", "setup", "teardown", "setUp", "tearDown",
    "toString", "equals", "hashCode", "get", "set", "new", "init"
}

# Regex to capture modified/added symbol definitions in diffs
SYMBOL_DEF_REGEX = re.compile(
    r"^\+[ \t]*(?:"
    r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("          # Python def foo(
    r"|func\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("         # GDScript/Swift func foo(
    r"|fun\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("          # Kotlin fun foo(
    r"|fn\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("           # Rust fn foo(
    r"|(?:public|private|protected|static|internal|override|async|virtual|inline|\s)+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*[{;]" # C#/Java/C++ method
    r"|class\s+([a-zA-Z_][a-zA-Z0-9_]*)"             # class Foo
    r"|class_name\s+([a-zA-Z_][a-zA-Z0-9_]*)"        # Godot class_name Foo
    r")",
    re.MULTILINE
)


COMMENT_PREFIXES = ("//", "#", "--", "/*", "*", "'''", '"""', "<!--", "REM ", "::")


class SymbolImpactRetriever:
    """Analyzes cross-file call sites and usages for functions and classes modified in a PR diff."""

    def __init__(self, root_dir: Optional[Path] = None, max_usages_per_symbol: int = 4, max_symbols: int = 8):
        self.root_dir = root_dir or Path.cwd()
        self.max_usages_per_symbol = max_usages_per_symbol
        self.max_symbols = max_symbols

    def extract_symbols_from_diff(self, diff_text: str) -> Set[str]:
        """Extracts newly added or modified function and class symbol names from git diff additions."""
        symbols: Set[str] = set()
        for line in diff_text.splitlines():
            if not line.startswith("+"):
                continue
            match = SYMBOL_DEF_REGEX.search(line)
            if match:
                # Find the non-empty matching capture group
                for g in match.groups():
                    if g and g not in IGNORED_SYMBOLS and len(g) > 2:
                        symbols.add(g)
        return symbols

    def find_cross_file_usages(
        self,
        symbols: Set[str],
        modified_files: Optional[Set[str]] = None,
    ) -> Dict[str, List[str]]:
        """Searches repository files for external usages and call sites of the given symbols.

        Returns a dictionary mapping symbol -> list of usage snippets (e.g. "path/to/file.py:L42: foo()").
        """
        if not symbols:
            return {}

        results: Dict[str, List[str]] = {}
        modified_files = modified_files or set()
        active_symbols = list(symbols)[:self.max_symbols]
        symbol_patterns = {
            sym: re.compile(r"\b" + re.escape(sym) + r"\b") for sym in active_symbols
        }

        # Scan code files in repository
        for file_path in self._walk_repo_files():
            rel_str = str(file_path.relative_to(self.root_dir))
            # Don't report calls within the file that defined it (we only care about cross-file impact)
            if rel_str in modified_files:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for sym, pattern in symbol_patterns.items():
                if sym not in content:
                    continue

                if sym not in results:
                    results[sym] = []

                if len(results[sym]) >= self.max_usages_per_symbol:
                    continue

                # Locate line numbers
                for idx, line in enumerate(content.splitlines(), start=1):
                    stripped = line.strip()
                    if not stripped or any(stripped.startswith(prefix) for prefix in COMMENT_PREFIXES):
                        continue

                    if pattern.search(line):
                        results[sym].append(f"`{rel_str}:L{idx}` {stripped[:100]}")
                        if len(results[sym]) >= self.max_usages_per_symbol:
                            break

        # Filter out symbols with 0 external usages
        return {k: v for k, v in results.items() if v}

    def _walk_repo_files(self) -> List[Path]:
        code_exts = {
            ".py", ".gd", ".cs", ".kt", ".java", ".swift",
            ".cpp", ".h", ".hpp", ".c", ".rs", ".ts", ".js"
        }
        collected: List[Path] = []
        for p in self.root_dir.rglob("*"):
            if p.is_file() and p.suffix in code_exts:
                parts = set(p.parts)
                if not parts.intersection(IGNORED_DIRS):
                    collected.append(p)
                    if len(collected) >= 300:  # Bound scan size for performance
                        break
        return collected
