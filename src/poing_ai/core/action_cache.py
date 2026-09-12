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

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from poing_ai.core.logging import get_logger
from poing_ai.core.models import ActionInput, ActionSchema

logger = get_logger("core.action_cache")

CACHE_VERSION = "1.0"


class ActionSchemaCache:
    """Persists parsed GitHub Action schemas to disk (.poing/cache/actions_schema.json)."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or (Path.cwd() / ".poing" / "cache")
        self.cache_file = self.cache_dir / "actions_schema.json"
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self.cache_file.exists():
            return
        try:
            raw_data = self.cache_file.read_text(encoding="utf-8", errors="replace")
            if not raw_data.strip():
                return
            data = json.loads(raw_data)
            if isinstance(data, dict) and data.get("version") == CACHE_VERSION:
                self._entries = data.get("entries", {})
        except Exception as e:
            logger.warning(f"Failed to load action schema cache from {self.cache_file}: {e}")
            self._entries = {}

    def get(self, action_ref: str) -> Optional[ActionSchema]:
        entry = self._entries.get(action_ref)
        if entry and isinstance(entry, dict):
            inputs_data = entry.get("inputs", {})
            inputs = {}
            for iname, idata in inputs_data.items():
                inputs[iname] = ActionInput(
                    name=iname,
                    description=idata.get("description", ""),
                    required=idata.get("required", False),
                    deprecated=idata.get("deprecated", False),
                    deprecation_message=idata.get("deprecation_message", ""),
                )
            return ActionSchema(
                action_ref=action_ref,
                exists=entry.get("exists", True),
                inputs=inputs,
            )
        return None

    def set(self, schema: ActionSchema) -> None:
        inputs_data = {}
        for iname, inp in schema.inputs.items():
            inputs_data[iname] = {
                "description": inp.description,
                "required": inp.required,
                "deprecated": inp.deprecated,
                "deprecation_message": inp.deprecation_message,
            }
        self._entries[schema.action_ref] = {
            "exists": schema.exists,
            "inputs": inputs_data,
            "updated_at": int(time.time()),
        }
        self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": CACHE_VERSION,
                "entries": self._entries,
            }
            tmp_file = self.cache_dir / "actions_schema.json.tmp"
            tmp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_file.replace(self.cache_file)
            self._dirty = False
            logger.info(f"💾 Action schema cache saved to {self.cache_file} ({len(self._entries)} entries).")
        except Exception as e:
            logger.warning(f"Failed to save action schema cache to {self.cache_file}: {e}")
