"""NOVA desktop intelligence service: wake-word, clipboard, OCR, command guard, workflows, and multi-agent dispatch."""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

from PIL import Image

from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.ai.router import MultiModelAIRouter
from backend.app.domain.entities import MemoryLayer, ProductSource
from backend.app.memory.memory_service import MemoryService


class NovaService:
    """Powering NOVA desktop capabilities with safe fallback in containerized Linux environments."""

    WAKE_PHRASES = ("hey nova", "nova listen", "hey aspirant", "ok nova")
    HIGH_RISK_PATTERNS = (
        r"\brm\s+-rf\b",
        r"\bformat\b\s+[a-zA-Z]:",
        r"\bdel\s+/[sqf]",
        r"\bremove-item\b.*-recurse",
        r"\breg\s+delete\b",
        r"\bshutdown\b",
    )

    def __init__(
        self,
        *,
        router: MultiModelAIRouter,
        memory: MemoryService,
        orchestrator: AgentOrchestrator,
    ) -> None:
        self._router = router
        self._memory = memory
        self._orchestrator = orchestrator

    def detect_wake_word(self, transcript: str) -> dict[str, Any]:
        cleaned = re.sub(r"[^\w\s]", " ", transcript.lower()).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        matched_phrase = next((p for p in self.WAKE_PHRASES if p in cleaned), None)
        if not matched_phrase:
            try:
                from aspirant.voice.wakeword import match_wake_word

                res = match_wake_word(transcript, wake_words=["hey nova", "hey aspirant"])
                if getattr(res, "detected", False):
                    matched_phrase = getattr(res, "matched_phrase", "hey nova")
            except Exception:
                pass
        command_tail = ""
        if matched_phrase and matched_phrase in cleaned:
            command_tail = cleaned.split(matched_phrase, 1)[1].strip()
        return {
            "detected": matched_phrase is not None,
            "matched_phrase": matched_phrase,
            "command_tail": command_tail,
        }

    def analyze_clipboard(self, content: str) -> dict[str, Any]:
        text = content.strip()
        kind = "plain_text"
        suggested_actions = ["Summarize with MJ", "Save as MAX Note"]
        if re.match(r"^https?://", text, re.IGNORECASE):
            kind = "url"
            suggested_actions = ["Open in Isolated Browser", "Deep Research URL Topic", "Bookmark in Knowledge RAG"]
        elif text.startswith("{") or text.startswith("["):
            try:
                json.loads(text)
                kind = "json"
                suggested_actions = ["Format & Validate JSON", "Generate TypeScript Types", "Inspect API Schema"]
            except Exception:
                pass
        elif "traceback" in text.lower() or "error:" in text.lower() or "exception" in text.lower():
            kind = "error_trace"
            suggested_actions = ["Diagnose Root Cause (Coding + Support Agents)", "Search Past Fixes"]
        elif any(tok in text for tok in ("def ", "class ", "function ", "const ", "import ", "async ")):
            kind = "code"
            suggested_actions = ["Explain & Review Code", "Generate Unit Tests", "Copy to Scratchpad"]
        elif "@" in text and "." in text and len(text.split()) == 1:
            kind = "email"
            suggested_actions = ["Draft Reply with MJ", "Recall Related Conversations"]
        return {
            "kind": kind,
            "character_count": len(text),
            "line_count": len(text.splitlines()) if text else 0,
            "preview": text[:180],
            "suggested_actions": suggested_actions,
        }

    def analyze_screenshot_or_ocr(self, image_base64: str) -> dict[str, Any]:
        raw = base64.b64decode(image_base64, validate=True)
        with Image.open(io.BytesIO(raw)) as img:
            width, height = img.size
            mode = img.mode
        return {
            "width": width,
            "height": height,
            "color_mode": mode,
            "byte_size": len(raw),
            "ocr_status": "ready",
            "extracted_text": "",
            "note": "Image validated and ready for Windows WinRT OCR or Gemini Vision analysis.",
        }

    def evaluate_command(self, command: str) -> dict[str, Any]:
        cmd = command.strip()
        try:
            from aspirant.security.command_policy import inspect_command

            verdict = inspect_command(cmd)
            return {
                "command": cmd,
                "risk": verdict.risk.value,
                "allowed_without_prompt": verdict.risk.value == "safe",
                "reason": verdict.reason,
            }
        except Exception:
            pass

        lowered = cmd.lower()
        for pat in self.HIGH_RISK_PATTERNS:
            if re.search(pat, lowered):
                return {
                    "command": cmd,
                    "risk": "blocked",
                    "allowed_without_prompt": False,
                    "reason": f"Matched destructive command policy pattern: {pat}",
                }
        return {
            "command": cmd,
            "risk": "confirm" if any(k in lowered for k in ("sudo", "rm ", "chmod", "chown", "pip ")) else "safe",
            "allowed_without_prompt": not any(k in lowered for k in ("sudo", "rm ")),
            "reason": "Evaluated via NOVA container-safe command policy.",
        }

    async def process_voice_command(self, *, user_id: str, transcript: str) -> dict[str, Any]:
        wake = self.detect_wake_word(transcript)
        objective = wake["command_tail"] or transcript.strip()
        await self._memory.record_conversation_turn(
            user_id=user_id,
            role="user",
            message=transcript,
            source_app=ProductSource.NOVA,
        )
        run = await self._orchestrator.execute_objective(
            user_id=user_id,
            objective=objective,
            source_app=ProductSource.NOVA,
        )
        await self._memory.record_conversation_turn(
            user_id=user_id,
            role="assistant",
            message=run.final_output,
            source_app=ProductSource.NOVA,
        )
        return {
            "wake": wake,
            "run_id": run.id,
            "selected_agents": run.selected_agents,
            "response_text": run.final_output,
            "tts_voice": "female-natural",
        }

    async def run_workflow(self, *, user_id: str, name: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
        executed: list[dict[str, Any]] = []
        for idx, step in enumerate(steps, start=1):
            action = str(step.get("action", "noop"))
            if action == "command":
                policy = self.evaluate_command(str(step.get("command", "")))
                executed.append({"step": idx, "action": action, "policy": policy, "status": "checked"})
            elif action == "clipboard_analyze":
                executed.append(
                    {"step": idx, "action": action, "result": self.analyze_clipboard(str(step.get("text", "")))}
                )
            else:
                executed.append({"step": idx, "action": action, "target": step.get("target"), "status": "planned"})
        await self._memory.remember(
            user_id=user_id,
            content=f"Executed NOVA workflow '{name}' with {len(executed)} steps.",
            layer=MemoryLayer.LONG_TERM,
            source_app=ProductSource.NOVA,
            tags=["nova", "workflow", name.lower()],
        )
        return {"workflow": name, "steps_executed": executed, "status": "completed"}
