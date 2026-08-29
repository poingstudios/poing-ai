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

import logging
import sys


class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[90m",       # Gray
        logging.INFO: "\033[36m",        # Cyan
        logging.WARNING: "\033[1;33m",   # Bold Yellow
        logging.ERROR: "\033[1;31m",     # Bold Red
        logging.CRITICAL: "\033[1;41m",  # Bold Red Background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        level_tag = f"{color}[{record.levelname}]{self.RESET}"
        name_tag = f"\033[90m[{record.name}]\033[0m"

        # Color message body for warnings and errors
        msg = record.getMessage()
        if record.levelno >= logging.WARNING:
            msg = f"{color}{msg}{self.RESET}"

        formatted = f"{level_tag} {name_tag} {msg}"

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                if formatted[-1:] != "\n":
                    formatted += "\n"
                formatted += record.exc_text

        if record.stack_info:
            if formatted[-1:] != "\n":
                formatted += "\n"
            formatted += self.formatStack(record.stack_info)

        return formatted


def get_logger(name: str = "poing_reviewer") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)
    return logger
