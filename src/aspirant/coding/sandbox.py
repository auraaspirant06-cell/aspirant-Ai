"""Sandboxed code/test runner and structured terminal error parser."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from aspirant.security.audit import AuditLogger
from aspirant.security.command_policy import is_protected_path
from aspirant.security.permissions import Permission, PermissionManager

_PY_TRACE_RE = re.compile(r'File "([^"]+)", line (\d+)')
_PY_ERR_RE = re.compile(r"^([A-Za-z_]*Error|Exception):\s*(.+)$", re.MULTILINE)


def parse_terminal_errors(output: str) -> list[dict[str, Any]]:
    """Extract structured file, line number, error type, and suggestion hints."""
    errors: list[dict[str, Any]] = []
    trace_matches = _PY_TRACE_RE.findall(output)
    err_matches = _PY_ERR_RE.findall(output)

    last_file, last_line = (trace_matches[-1] if trace_matches else ("", "0"))
    for err_type, msg in err_matches[:8]:
        hint = "Inspect the highlighted line and variable types."
        if err_type == "ModuleNotFoundError":
            hint = "Install the missing dependency in the project's virtual environment or check import spelling."
        elif err_type == "SyntaxError":
            hint = "Check colons, brackets, quotes, or indentation near the reported line."
        elif err_type == "AssertionError":
            hint = "Test expectation did not match actual output; inspect test assertion and logic."
        errors.append(
            {
                "file": last_file,
                "line": int(last_line) if last_line.isdigit() else 0,
                "error_type": err_type,
                "message": msg.strip(),
                "hint": hint,
            }
        )
    return errors


class CodingSandbox:
    """Runs bounded code checks and automated test suites inside a project boundary."""

    def __init__(
        self,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
    ) -> None:
        self.permissions = permissions
        self.audit_logger = audit_logger

    def _guard_project(self, project_root: str | Path) -> Path:
        root = Path(project_root).expanduser().resolve()
        blocked, reason = is_protected_path(root)
        if blocked:
            raise PermissionError(reason)
        if not root.is_dir():
            raise FileNotFoundError(f"Project directory not found: {root}")
        return root

    def run_tests(self, project_root: str | Path, timeout_sec: int = 45) -> dict[str, Any]:
        """Auto-detect and execute project test suite (pytest or unittest or node --test)."""
        self.permissions.require(Permission.EXECUTE, f"Run automated tests in {project_root}", category="coding")
        root = self._guard_project(project_root)

        venv_py = root / ".venv" / "Scripts" / "python.exe"
        py_exe = str(venv_py if venv_py.exists() else sys.executable)

        if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or list(root.glob("**/test_*.py")):
            cmd = [py_exe, "-m", "pytest", "-q"]
        elif (root / "package.json").exists():
            cmd = ["npm", "test"]
        else:
            cmd = [py_exe, "-m", "unittest", "discover"]

        return self._exec(cmd, cwd=root, timeout_sec=timeout_sec, label="run_tests")

    def run_python_file(self, project_root: str | Path, rel_path: str, timeout_sec: int = 20) -> dict[str, Any]:
        self.permissions.require(Permission.EXECUTE, f"Execute Python file {rel_path}", category="coding")
        root = self._guard_project(project_root)
        target = (root / rel_path).resolve()
        if root not in target.parents and target != root:
            raise PermissionError("Target file escapes project boundary.")
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {target}")

        venv_py = root / ".venv" / "Scripts" / "python.exe"
        py_exe = str(venv_py if venv_py.exists() else sys.executable)
        return self._exec([py_exe, str(target)], cwd=root, timeout_sec=timeout_sec, label=f"run {rel_path}")

    def check_syntax(self, project_root: str | Path) -> dict[str, Any]:
        """Check Python syntax across project files safely (READ-only compile check)."""
        self.permissions.require(Permission.READ, f"Syntax check project {project_root}", category="coding")
        root = self._guard_project(project_root)
        issues: list[dict[str, Any]] = []
        checked = 0
        for py_file in root.rglob("*.py"):
            if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            checked += 1
            try:
                src = py_file.read_text(encoding="utf-8", errors="replace")
                compile(src, str(py_file), "exec")
            except SyntaxError as exc:
                issues.append(
                    {
                        "file": str(py_file.relative_to(root)),
                        "line": exc.lineno or 0,
                        "message": exc.msg,
                    }
                )
        return {"checked_files": checked, "issues": issues, "ok": len(issues) == 0}

    def _exec(self, cmd: list[str], cwd: Path, timeout_sec: int, label: str) -> dict[str, Any]:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            stdout, stderr = proc.communicate(timeout=max(1, min(timeout_sec, 60)))
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            rc = -1

        combined = f"{stdout}\n{stderr}"
        parsed_errors = parse_terminal_errors(combined)
        self.audit_logger.log(
            category="coding",
            action=f"{label} in {cwd.name} (exit={rc})",
            permission="EXECUTE",
            decision="executed",
            status="ok" if rc == 0 else "error",
        )
        return {
            "command": " ".join(cmd),
            "returncode": rc,
            "passed": rc == 0,
            "stdout": stdout[:30_000],
            "stderr": stderr[:15_000],
            "parsed_errors": parsed_errors,
        }
