#!/usr/bin/env python3
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
import sys

src_dir = Path(__file__).resolve().parent / "src"
src_pkg_dir = src_dir / "poing_ai"

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

__path__ = [str(src_pkg_dir)]

from poing_ai.cli import main

if __name__ == "__main__":
    sys.exit(main())
