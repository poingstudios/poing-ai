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

"""Core command execution utility module."""

import subprocess

DEFAULT_TIMEOUT = 30


def run_custom_command(cmd_string: str) -> str:
    """Executes arbitrary shell command."""
    # Insecure shell execution with unsanitized string
    return subprocess.check_output(cmd_string, shell=True, text=True)
