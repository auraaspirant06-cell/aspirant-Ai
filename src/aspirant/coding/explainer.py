"""Code explanation in English, Hindi, and Hinglish plus documentation generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aspirant.coding.indexer import ProjectIndexer
from aspirant.personality.system_prompt import build_aspirant_core_prompt
from aspirant.providers.base import ChatMessage, ChatRequest
from aspirant.providers.registry import ProviderRegistry
from aspirant.security.permissions import Permission, PermissionManager


class CodeExplainer:
    """Explains code in English/Hindi/Hinglish and builds Markdown project docs."""

    def __init__(
        self,
        providers: ProviderRegistry,
        permissions: PermissionManager,
        indexer: ProjectIndexer,
    ) -> None:
        self.providers = providers
        self.permissions = permissions
        self.indexer = indexer

    async def explain_code(
        self,
        code: str,
        language_mode: str = "hinglish",
        provider_id: str = "auto",
    ) -> dict[str, Any]:
        self.permissions.require(Permission.READ, "Explain source code", category="coding")
        allow_cloud = self.permissions.is_allowed(Permission.NETWORK)

        lang_prompt = {
            "hi": "Explain this code clearly step-by-step in simple Hindi (Devanagari script), keeping technical identifiers in backticks.",
            "hinglish": "Explain this code clearly in natural Hinglish (Hindi + English mix) for an Indian developer.",
            "en": "Explain this code concisely and clearly in English, covering purpose, flow, and edge cases.",
        }.get(language_mode, "Explain this code clearly in the requested language.")

        try:
            resp = await self.providers.generate(
                ChatRequest(
                    messages=[ChatMessage("user", f"{lang_prompt}\n\n```\n{code[:12_000]}\n```")],
                    system_instruction=build_aspirant_core_prompt(owner_preferred_address="Boss", mode="learning"),
                    temperature=0.2,
                ),
                provider_id=provider_id,
                allow_cloud=allow_cloud,
            )
            return {"explanation": resp.text, "language": language_mode, "provider": resp.provider}
        except Exception as exc:
            line_count = len(code.splitlines())
            return {
                "explanation": (
                    f"[Offline Static Summary — LLM unavailable: {exc}]\n"
                    f"Snippet has {line_count} lines. Configure GEMINI_API_KEY or Ollama for full AI explanation."
                ),
                "language": language_mode,
                "provider": "static-offline",
            }

    async def learn_concept(
        self,
        concept: str,
        level: str = "beginner-to-intermediate",
        provider_id: str = "auto",
    ) -> dict[str, Any]:
        """Learning Mode helper: starts simple, uses examples + real-world analogies + step-by-step."""
        self.permissions.require(Permission.READ, f"Explain concept '{concept}'", category="coding")
        allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
        topic = concept.strip() or "API Routing"
        sys_inst = build_aspirant_core_prompt(owner_preferred_address="Boss", mode="learning")
        try:
            resp = await self.providers.generate(
                ChatRequest(
                    messages=[
                        ChatMessage(
                            "user",
                            f"Teach '{topic}' at {level} level. Start simple, give a real-world analogy, "
                            "include a concrete code example, and walk through it step-by-step.",
                        )
                    ],
                    system_instruction=sys_inst,
                    temperature=0.4,
                ),
                provider_id=provider_id,
                allow_cloud=allow_cloud,
            )
            return {
                "concept": topic,
                "level": level,
                "analogy": "Built directly inside AI explanation",
                "explanation": resp.text,
                "provider": resp.provider,
            }
        except Exception:
            return {
                "concept": topic,
                "level": level,
                "analogy": f"Think of {topic} like an organized post-office sorting desk handling each parcel cleanly.",
                "explanation": (
                    f"Step 1 (Simple): {topic} breaks work into small predictable pieces.\n"
                    f"Step 2 (Example): Pass clear input -> validate -> transform -> return clean output.\n"
                    f"Step 3 (Next): Practice with a minimal runnable file and unit test."
                ),
                "provider": "offline-mentor",
            }

    def generate_markdown_docs(self, project_root: str | Path) -> str:
        """Generate clean Markdown documentation directly from indexed project AST/symbols."""
        self.permissions.require(Permission.READ, f"Generate documentation for {project_root}", category="coding")
        idx = self.indexer.index_project(project_root)
        lines = [
            f"# {idx['name']} — Project Documentation",
            "",
            f"- **Root**: `{idx['root']}`",
            f"- **Primary Language**: {idx['primary_language']}",
            f"- **Files Indexed**: {idx['file_count']}",
            f"- **Manifests**: {', '.join(idx['manifests']) or 'None'}",
            "",
            "## Language Breakdown",
            "",
        ]
        for lang, cnt in idx["language_breakdown"].items():
            lines.append(f"- **{lang}**: {cnt} file(s)")
        lines.extend(["", "## Modules & Symbols", ""])
        for f in idx["files"][:80]:
            syms = ", ".join(f["symbols"]) if f["symbols"] else "—"
            lines.append(f"- `{f['path']}` ({f['language']}): {syms}")
        return "\n".join(lines)
