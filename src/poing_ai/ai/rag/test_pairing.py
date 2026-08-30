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
from typing import Dict, Iterable, List, Optional, Set

from poing_ai.core.logging import get_logger

logger = get_logger("ai.rag.test_pairing")

# Common test directory names
TEST_DIRS = ["tests", "test", "spec", "specs", "UnitTests", "Tests"]


class TestPairingRetriever:
    """Discovers and loads associated unit test files for modified source code files."""

    def __init__(self, root_dir: Optional[Path] = None, max_chars_per_test: int = 15000):
        self.root_dir = root_dir or Path.cwd()
        self.max_chars_per_test = max_chars_per_test

    def find_associated_tests(self, file_paths: Iterable[str]) -> Dict[str, str]:
        """Finds matching test file contents for a set of modified source files.

        Returns a dictionary mapping source file path to test file content.
        """
        results: Dict[str, str] = {}
        seen_test_paths: Set[Path] = set()

        for fpath in file_paths:
            path_obj = Path(fpath)
            # Skip if the modified file itself is already a test file
            if self._is_test_file(path_obj):
                continue

            candidates = self._generate_candidate_test_paths(path_obj)
            for candidate in candidates:
                abs_candidate = (self.root_dir / candidate).resolve()
                if abs_candidate.exists() and abs_candidate.is_file() and abs_candidate not in seen_test_paths:
                    seen_test_paths.add(abs_candidate)
                    try:
                        content = abs_candidate.read_text(encoding="utf-8", errors="replace")
                        if len(content) > self.max_chars_per_test:
                            content = content[:self.max_chars_per_test] + "\n... [Test content truncated]"
                        results[str(candidate)] = content
                        logger.info(f"Paired test file `{candidate}` with modified source `{fpath}`")
                    except Exception as e:
                        logger.warning(f"Failed to read test file {abs_candidate}: {e}")
                    break

        return results

    def _is_test_file(self, path: Path) -> bool:
        name_lower = path.name.lower()
        parts_lower = [p.lower() for p in path.parts]
        if any(td.lower() in parts_lower for td in TEST_DIRS):
            return True
        return (
            name_lower.startswith("test_")
            or name_lower.endswith("_test.py")
            or name_lower.endswith("_test.gd")
            or name_lower.endswith("test.cs")
            or name_lower.endswith("tests.cs")
            or name_lower.endswith("tests.swift")
        )

    def _generate_candidate_test_paths(self, path: Path) -> List[Path]:
        stem = path.stem
        suffix = path.suffix
        candidates: List[Path] = []

        # Common test naming variations
        test_filenames = [
            f"test_{stem}{suffix}",
            f"{stem}_test{suffix}",
            f"{stem}Test{suffix}",
            f"{stem}Tests{suffix}",
            f"Test{stem}{suffix}",
        ]

        # 1. Look in sibling tests/ or test/ subdirectories
        for td in TEST_DIRS:
            for tf in test_filenames:
                candidates.append(path.parent / td / tf)

        # 2. Look in root-level test directories mirroring the relative path
        for td in TEST_DIRS:
            for tf in test_filenames:
                # e.g. tests/test_foo.py or tests/services/test_foo.py
                candidates.append(Path(td) / tf)
                if len(path.parts) > 1:
                    candidates.append(Path(td) / Path(*path.parts[1:-1]) / tf)

        # 3. Same directory as source file
        for tf in test_filenames:
            candidates.append(path.parent / tf)

        return candidates
