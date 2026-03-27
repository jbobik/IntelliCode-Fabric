"""
Agent Tools v1.0 — реальные инструменты для мультиагентной системы.

Каждый инструмент — это атомарное действие, которое агент может вызвать:
- read_file: прочитать файл из проекта
- write_file: создать/перезаписать файл
- edit_file: точечная правка файла (replace)
- run_command: выполнить shell-команду
- search_code: поиск по кодовой базе (grep)
- list_files: просмотр структуры директории
"""

import asyncio
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Ограничения безопасности
MAX_FILE_SIZE = 100_000  # 100KB
MAX_OUTPUT_SIZE = 50_000  # 50KB
COMMAND_TIMEOUT = 30  # секунд
BLOCKED_COMMANDS = [
    "rm -rf /", "rm -rf /*", "format", "mkfs",
    ":(){ :|:& };:", "dd if=/dev/zero",
    "shutdown", "reboot", "halt",
    "sudo rm -rf", "sudo mkfs", "sudo dd",
]
BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/(?!\w)",  # rm -rf / (но не rm -rf /some/path)
    r">\s*/dev/sd",
]


class ToolResult:
    """Результат выполнения инструмента"""
    def __init__(self, success: bool, output: str, tool_name: str, metadata: dict = None):
        self.success = success
        self.output = output
        self.tool_name = tool_name
        self.metadata = metadata or {}

    def to_dict(self):
        return {
            "success": self.success,
            "output": self.output[:MAX_OUTPUT_SIZE],
            "tool": self.tool_name,
            **self.metadata,
        }

    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"[{status} {self.tool_name}] {self.output[:500]}"


class AgentToolkit:
    """
    Набор инструментов, доступных агентам.

    Привязан к workspace_root — все операции ограничены этой директорией.
    """

    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root) if workspace_root else None
        self.command_history: list[dict] = []
        self.file_changes: list[dict] = []  # Трекаем все изменения файлов

    def set_workspace(self, path: str):
        self.workspace_root = Path(path)

    def _resolve_path(self, file_path: str) -> Path:
        """Резолвит путь относительно workspace, проверяет безопасность."""
        p = Path(file_path)
        if not p.is_absolute():
            if self.workspace_root:
                p = self.workspace_root / p
            else:
                raise ValueError("No workspace root set and path is relative")

        # Resolve symlinks and check workspace boundaries
        resolved = p.resolve()
        if self.workspace_root:
            workspace_resolved = self.workspace_root.resolve()
            try:
                resolved.relative_to(workspace_resolved)
            except ValueError:
                raise ValueError(f"Path escapes workspace: {file_path}")

        return resolved

    # ─── READ FILE ────────────────────────────────────────────────────

    async def read_file(self, file_path: str, line_start: int = None, line_end: int = None) -> ToolResult:
        """Читает файл из проекта"""
        try:
            p = self._resolve_path(file_path)
            if not p.exists():
                return ToolResult(False, f"File not found: {file_path}", "read_file")
            if not p.is_file():
                return ToolResult(False, f"Not a file: {file_path}", "read_file")
            if p.stat().st_size > MAX_FILE_SIZE:
                return ToolResult(False, f"File too large: {p.stat().st_size} bytes", "read_file")

            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")

            if line_start is not None or line_end is not None:
                start = max(0, (line_start or 1) - 1)
                end = min(len(lines), line_end or len(lines))
                selected = lines[start:end]
                numbered = "\n".join(f"{start + i + 1:4d} | {line}" for i, line in enumerate(selected))
                return ToolResult(True, numbered, "read_file", {
                    "file_path": str(p),
                    "lines": len(selected),
                    "total_lines": len(lines),
                })
            else:
                numbered = "\n".join(f"{i + 1:4d} | {line}" for i, line in enumerate(lines))
                return ToolResult(True, numbered, "read_file", {
                    "file_path": str(p),
                    "lines": len(lines),
                })

        except Exception as e:
            return ToolResult(False, f"Error reading file: {e}", "read_file")

    # ─── WRITE FILE ───────────────────────────────────────────────────

    async def write_file(self, file_path: str, content: str) -> ToolResult:
        """Создаёт или перезаписывает файл"""
        try:
            p = self._resolve_path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

            self.file_changes.append({
                "action": "write",
                "file": str(p),
                "lines": content.count("\n") + 1,
            })

            return ToolResult(True, f"File written: {file_path} ({content.count(chr(10)) + 1} lines)", "write_file", {
                "file_path": str(p),
                "created": True,
            })
        except Exception as e:
            return ToolResult(False, f"Error writing file: {e}", "write_file")

    # ─── EDIT FILE ────────────────────────────────────────────────────

    async def edit_file(self, file_path: str, old_text: str, new_text: str) -> ToolResult:
        """Точечная правка файла: замена old_text → new_text"""
        try:
            p = self._resolve_path(file_path)
            if not p.exists():
                return ToolResult(False, f"File not found: {file_path}", "edit_file")

            content = p.read_text(encoding="utf-8", errors="replace")
            count = content.count(old_text)

            if count == 0:
                return ToolResult(False, f"Text not found in {file_path}", "edit_file")
            if count > 1:
                return ToolResult(False, f"Ambiguous: found {count} occurrences. Provide more context.", "edit_file")

            new_content = content.replace(old_text, new_text, 1)
            p.write_text(new_content, encoding="utf-8")

            self.file_changes.append({
                "action": "edit",
                "file": str(p),
                "old_text": old_text[:100],
                "new_text": new_text[:100],
            })

            return ToolResult(True, f"File edited: {file_path}", "edit_file", {
                "file_path": str(p),
                "replacements": 1,
            })
        except Exception as e:
            return ToolResult(False, f"Error editing file: {e}", "edit_file")

    # ─── RUN COMMAND ──────────────────────────────────────────────────

    async def run_command(self, command: str, cwd: str = None) -> ToolResult:
        """Выполняет shell-команду в директории проекта"""
        # Проверка безопасности
        cmd_lower = command.lower().strip()
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return ToolResult(False, f"Blocked dangerous command: {command}", "run_command")
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, cmd_lower):
                return ToolResult(False, f"Blocked dangerous pattern in: {command}", "run_command")

        work_dir = cwd or str(self.workspace_root or ".")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT,
                cwd=work_dir,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            ))

            output = ""
            if result.stdout:
                output += result.stdout[:MAX_OUTPUT_SIZE]
            if result.stderr:
                output += ("\n--- stderr ---\n" + result.stderr[:MAX_OUTPUT_SIZE // 2])

            self.command_history.append({
                "command": command,
                "returncode": result.returncode,
                "cwd": work_dir,
            })

            return ToolResult(
                success=(result.returncode == 0),
                output=output.strip() or f"Command exited with code {result.returncode}",
                tool_name="run_command",
                metadata={
                    "command": command,
                    "returncode": result.returncode,
                    "cwd": work_dir,
                },
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, f"Command timed out after {COMMAND_TIMEOUT}s: {command}", "run_command")
        except Exception as e:
            return ToolResult(False, f"Error running command: {e}", "run_command")

    # ─── SEARCH CODE ──────────────────────────────────────────────────

    async def search_code(self, query: str, file_pattern: str = "*", max_results: int = 20) -> ToolResult:
        """Поиск по содержимому файлов (grep-подобный)"""
        if not self.workspace_root:
            return ToolResult(False, "No workspace root set", "search_code")

        try:
            results = []
            pattern = re.compile(re.escape(query), re.IGNORECASE)

            ignore_dirs = {
                "node_modules", ".git", "__pycache__", ".venv", "venv",
                "dist", "build", ".next", ".cache", "out",
            }

            for root, dirs, files in os.walk(self.workspace_root):
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                for fname in files:
                    if file_pattern != "*":
                        from fnmatch import fnmatch
                        if not fnmatch(fname, file_pattern):
                            continue

                    fpath = Path(root) / fname
                    try:
                        if fpath.stat().st_size > MAX_FILE_SIZE:
                            continue
                        content = fpath.read_text(encoding="utf-8", errors="replace")
                        for i, line in enumerate(content.split("\n"), 1):
                            if pattern.search(line):
                                rel = fpath.relative_to(self.workspace_root)
                                results.append(f"{rel}:{i}: {line.strip()}")
                                if len(results) >= max_results:
                                    break
                    except (UnicodeDecodeError, PermissionError):
                        continue

                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break

            if not results:
                return ToolResult(True, f"No matches found for '{query}'", "search_code")

            output = "\n".join(results)
            return ToolResult(True, output, "search_code", {
                "matches": len(results),
                "query": query,
            })
        except Exception as e:
            return ToolResult(False, f"Search error: {e}", "search_code")

    # ─── LIST FILES ───────────────────────────────────────────────────

    async def list_files(self, directory: str = ".", max_depth: int = 3) -> ToolResult:
        """Показывает структуру директории"""
        try:
            p = self._resolve_path(directory)
            if not p.exists():
                return ToolResult(False, f"Directory not found: {directory}", "list_files")
            if not p.is_dir():
                return ToolResult(False, f"Not a directory: {directory}", "list_files")

            ignore_dirs = {
                "node_modules", ".git", "__pycache__", ".venv", "venv",
                "dist", "build", ".next", ".cache", "out", ".mypy_cache",
            }

            lines = []

            def walk(current: Path, prefix: str, depth: int):
                if depth > max_depth:
                    return
                try:
                    entries = sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                except PermissionError:
                    return

                dirs = [e for e in entries if e.is_dir() and e.name not in ignore_dirs]
                files = [e for e in entries if e.is_file()]

                for d in dirs:
                    lines.append(f"{prefix}📁 {d.name}/")
                    walk(d, prefix + "  ", depth + 1)
                for f in files:
                    size = f.stat().st_size
                    size_str = f"{size}B" if size < 1024 else f"{size // 1024}KB"
                    lines.append(f"{prefix}📄 {f.name} ({size_str})")

            walk(p, "", 0)
            output = "\n".join(lines[:200])
            if len(lines) > 200:
                output += f"\n... and {len(lines) - 200} more entries"

            return ToolResult(True, output, "list_files", {"entries": len(lines)})
        except Exception as e:
            return ToolResult(False, f"Error listing files: {e}", "list_files")

    # ─── Tool registry ────────────────────────────────────────────────

    def get_tools_description(self) -> str:
        """Возвращает описание всех инструментов для промпта LLM"""
        return """Available tools (call by outputting a JSON block with "tool" and "args"):

1. **read_file** — Read a file from the project
   Args: {"file_path": "path/to/file", "line_start": 1, "line_end": 50}  (line_start/line_end optional)

2. **write_file** — Create or overwrite a file
   Args: {"file_path": "path/to/file", "content": "file content here"}

3. **edit_file** — Make a precise edit (find & replace)
   Args: {"file_path": "path/to/file", "old_text": "text to find", "new_text": "replacement text"}

4. **run_command** — Execute a shell command
   Args: {"command": "npm test", "cwd": "optional/directory"}

5. **search_code** — Search code files for a pattern
   Args: {"query": "search term", "file_pattern": "*.py", "max_results": 20}

6. **list_files** — List directory structure
   Args: {"directory": "src/", "max_depth": 3}

To use a tool, output EXACTLY this format on its own line:
```tool
{"tool": "tool_name", "args": {...}}
```
You may call multiple tools. After each tool call, you will receive the result and can decide next steps.
When you are done and have a final answer, output your response WITHOUT any tool calls."""

    async def execute_tool(self, tool_name: str, args: dict) -> ToolResult:
        """Выполняет инструмент по имени"""
        tool_map = {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "edit_file": self.edit_file,
            "run_command": self.run_command,
            "search_code": self.search_code,
            "list_files": self.list_files,
        }

        fn = tool_map.get(tool_name)
        if not fn:
            return ToolResult(False, f"Unknown tool: {tool_name}", tool_name)

        try:
            return await fn(**args)
        except TypeError as e:
            return ToolResult(False, f"Invalid args for {tool_name}: {e}", tool_name)
        except Exception as e:
            return ToolResult(False, f"Tool error: {e}", tool_name)

    def get_changes_summary(self) -> list[dict]:
        """Возвращает список всех изменений файлов для UI"""
        return self.file_changes.copy()
