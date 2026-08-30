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

import os
from pathlib import Path
import subprocess
import sys
from typing import Dict, Iterable, List, Optional, Set, Tuple


IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".svg", ".zip", ".tar", ".gz", ".aar",
    ".jar", ".dylib", ".so", ".dll", ".a", ".framework", ".xcframework",
    ".resolved", ".lock", ".ico", ".webp", ".mp3", ".wav", ".ogg",
    ".bank", ".tscn", ".blend", ".fbx", ".obj"
}
MAX_FILE_SIZE_BYTES = 100 * 1024


def load_file_contents_for_diff(
    file_paths: Iterable[str],
    root_dir: Optional[Path] = None,
    head_sha: Optional[str] = None,
) -> Dict[str, str]:
    base = root_dir or Path.cwd()
    file_contents: Dict[str, str] = {}
    for rel_path in file_paths:
        if any(rel_path.endswith(ext) for ext in IGNORED_EXTENSIONS):
            continue

        content = ""
        if head_sha:
            try:
                proc = subprocess.run(
                    ["git", "show", f"{head_sha}:{rel_path}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(base),
                    text=True,
                )
                if proc.returncode == 0:
                    content = proc.stdout
            except Exception:
                pass

        if not content:
            full_path = base / rel_path
            if full_path.exists() and not full_path.is_dir():
                try:
                    if full_path.stat().st_size <= MAX_FILE_SIZE_BYTES:
                        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                except Exception as e:
                    print(f"Warning: Could not read file content for {rel_path}: {e}", file=sys.stderr)

        if content and len(content.encode("utf-8")) <= MAX_FILE_SIZE_BYTES:
            file_contents[rel_path] = content

    return file_contents


def _run_git_diff_cmd(cmd: List[str], cwd: Optional[str] = None) -> str:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            text=True,
        )
        if proc.returncode == 0:
            return proc.stdout
    except Exception:
        pass
    return ""


def get_git_diff(
    base_ref: str = "master",
    local: bool = False,
    staged: bool = False,
    diff_target: Optional[str] = None,
    files: Optional[List[str]] = None,
    root_dir: Optional[Path] = None,
    head_sha: Optional[str] = None,
) -> str:
    cwd = str(root_dir) if root_dir else None
    file_args = ["--"] + files if files else []

    if diff_target:
        return _run_git_diff_cmd(["git", "diff", diff_target] + file_args, cwd=cwd)

    if staged:
        return _run_git_diff_cmd(["git", "diff", "--cached"] + file_args, cwd=cwd)

    if files:
        diff = _run_git_diff_cmd(["git", "diff", "HEAD"] + file_args, cwd=cwd)
        if not diff.strip() and head_sha:
            diff = _run_git_diff_cmd(["git", "diff", f"origin/{base_ref}...{head_sha}"] + file_args, cwd=cwd)
        if not diff.strip():
            diff = _run_git_diff_cmd(["git", "diff", f"{base_ref}...HEAD"] + file_args, cwd=cwd)
        return diff

    if local:
        # Check combined staged + unstaged changes first
        diff = _run_git_diff_cmd(["git", "diff", "HEAD"], cwd=cwd)
        if not diff.strip():
            diff = _run_git_diff_cmd(["git", "diff", f"{base_ref}...HEAD"], cwd=cwd)
        if not diff.strip():
            diff = _run_git_diff_cmd(["git", "diff", base_ref], cwd=cwd)
        return diff

    # CI Mode (pull_request or pull_request_target)
    diff = ""
    if head_sha:
        diff = _run_git_diff_cmd(["git", "diff", f"origin/{base_ref}...{head_sha}"] + file_args, cwd=cwd)
        if not diff.strip():
            diff = _run_git_diff_cmd(["git", "diff", f"{base_ref}...{head_sha}"] + file_args, cwd=cwd)

    if not diff.strip():
        diff = _run_git_diff_cmd(["git", "diff", f"origin/{base_ref}...HEAD"] + file_args, cwd=cwd)

    if not diff.strip():
        diff = _run_git_diff_cmd(["git", "diff", f"{base_ref}...HEAD"] + file_args, cwd=cwd)

    if not diff.strip():
        diff = _run_git_diff_cmd(["git", "diff", f"origin/{base_ref}...FETCH_HEAD"] + file_args, cwd=cwd)

    return diff


def annotate_diff(diff_text: str) -> Tuple[str, Set[Tuple[str, int]]]:
    lines = diff_text.splitlines()
    annotated: List[str] = []
    current_file: Optional[str] = None
    new_line_num = 0
    valid_lines: Set[Tuple[str, int]] = set()

    for line in lines:
        if line.startswith("diff --git"):
            parts = line.split(" ")
            if len(parts) >= 4:
                current_file = parts[3][2:]
            new_line_num = 0
            annotated.append(line)
        elif line.startswith("+++ b/"):
            current_file = line[6:]
            annotated.append(line)
        elif line.startswith("--- a/") or line.startswith("index "):
            annotated.append(line)
        elif line.startswith("\\ No newline at end of file"):
            annotated.append(line)
        elif line.startswith("@@"):
            annotated.append(line)
            try:
                header = line.split("@@")[1].strip()
                new_part = header.split(" ")[1]
                new_start = int(new_part.split(",")[0][1:])
                new_line_num = new_start
            except (ValueError, IndexError):
                pass
        elif current_file:
            if line.startswith("+"):
                annotated.append(f"[{current_file} L{new_line_num}] {line}")
                valid_lines.add((current_file, new_line_num))
                new_line_num += 1
            elif line.startswith("-"):
                annotated.append(f"[{current_file} DELETED] {line}")
            else:
                annotated.append(f"[{current_file} L{new_line_num}] {line}")
                valid_lines.add((current_file, new_line_num))
                new_line_num += 1
        else:
            annotated.append(line)

    return "\n".join(annotated), valid_lines


def split_diff_by_file(diff_text: str) -> List[str]:
    lines = diff_text.splitlines(keepends=True)
    blocks: List[str] = []
    current: List[str] = []
    for line in lines:
        if line.startswith("diff --git") and current:
            blocks.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("".join(current))
    return blocks


def split_batches(file_blocks: List[str], max_chars: int) -> List[List[str]]:
    batches: List[List[str]] = []
    current: List[str] = []
    current_size = 0
    for block in file_blocks:
        if current and current_size + len(block) > max_chars:
            batches.append(current)
            current = []
            current_size = 0
        current.append(block)
        current_size += len(block)
    if current:
        batches.append(current)
    return batches
