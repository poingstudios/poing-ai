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


class GenericAnalyzer(BaseEngineAnalyzer):
    @property
    def name(self) -> str:
        return "Generic Repository"

    def get_file_patterns(self) -> List[str]:
        return ["*"]

    def get_review_guidelines(self) -> str:
        return """### General Software Engineering Guidelines
- **SOLID Principles**: Maintain Single Responsibility and clean dependency inversion across modules.
- **Error Handling**: Handle edge cases and unexpected exceptions explicitly; do not swallow errors silently.
- **Resource Management**: Always ensure opened files, network streams, and locks are released safely.
- **Security**: Never commit hardcoded tokens, passwords, or credentials."""
