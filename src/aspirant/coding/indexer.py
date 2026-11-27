"""Project structure reader, multi-language detector, and AST/symbol indexer."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
import re
from typing import Any

SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".next",
        ".idea",
        ".vscode",
    }
)

EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cc": "C++",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".md": "Markdown",
    ".json": "JSON",
    ".toml": "TOML",
}

_GENERIC_SYMBOL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|func|public\s+class|struct)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def _extract_symbols(path: Path, language: str) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    if language == "Python":
        try:
            tree = ast.parse(text)
            symbols: list[str] = []
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    prefix = "class" if isinstance(node, ast.ClassDef) else "def"
                    symbols.append(f"{prefix} {node.name}")
            return symbols[:30]
        except SyntaxError:
            return ["<SyntaxError>"]
    if language in {"JavaScript", "TypeScript", "Go", "Java", "C", "C++"}:
        return _GENERIC_SYMBOL_RE.findall(text)[:25]
    return []


class ProjectIndexer:
    """Scans a workspace safely and summarizes structure, languages, symbols, and tests."""

    def index_project(self, project_root: str | Path, max_files: int = 350) -> dict[str, Any]:
        root = Path(project_root).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Project directory not found: {root}")

        files: list[dict[str, Any]] = []
        lang_counts: Counter[str] = Counter()
        has_tests = False

        for item in sorted(root.rglob("*")):
            if any(part in SKIP_DIRS for part in item.relative_to(root).parts):
                continue
            if not item.is_file():
                continue
            rel = str(item.relative_to(root))
            lang = EXTENSION_LANGUAGE.get(item.suffix.lower(), "Other")
            if lang != "Other":
                lang_counts[lang] += 1
            if "test" in item.name.lower():
                has_tests = True
            symbols = _extract_symbols(item, lang) if len(files) < 120 else []
            files.append(
                {
                    "path": rel,
                    "language": lang,
                    "size_bytes": item.stat().st_size,
                    "symbols": symbols,
                }
            )
            if len(files) >= max_files:
                break

        manifests = [
            name
            for name in ("pyproject.toml", "requirements.txt", "package.json", "go.mod", "pom.xml", "CMakeLists.txt")
            if (root / name).exists()
        ]
        primary_lang = lang_counts.most_common(1)[0][0] if lang_counts else "Unknown"
        return {
            "root": str(root),
            "name": root.name,
            "primary_language": primary_lang,
            "language_breakdown": dict(lang_counts),
            "manifests": manifests,
            "has_tests": has_tests,
            "file_count": len(files),
            "files": files,
        }
