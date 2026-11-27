"""Orchestrates multilingual adaptive chat turns with memory and security gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator

from aspirant.memory.store import MemoryStore
from aspirant.personality.language_detect import LanguageProfile, detect_language
from aspirant.personality.personas import (
    detect_persona_switch_command,
    get_persona,
)
from aspirant.personality.style_adapter import analyze_style, build_system_instruction
from aspirant.providers.base import ChatMessage, ChatRequest, ChatResponse
from aspirant.providers.registry import ProviderRegistry
from aspirant.security.audit import AuditLogger
from aspirant.security.permissions import Permission, PermissionManager


@dataclass(frozen=True, slots=True)
class PreparedTurn:
    conversation_id: str
    persona_id: str
    switched_persona: str | None
    language: LanguageProfile
    style_summary: str
    chat_request: ChatRequest


class ChatService:
    """Connects adaptive personality, multilingual detection, memory, and LLM providers."""

    def __init__(
        self,
        memory: MemoryStore,
        providers: ProviderRegistry,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
    ) -> None:
        self.memory = memory
        self.providers = providers
        self.permissions = permissions
        self.audit_logger = audit_logger

    def prepare_turn(
        self,
        user_text: str,
        conversation_id: str | None = None,
        persona_id: str = "professional",
        language_override: str = "auto",
        model: str | None = None,
    ) -> PreparedTurn:
        """Detect language, style, and persona switches, and store user turn safely."""
        self.permissions.require(Permission.READ, "Prepare chat context", category="chat")

        switched = detect_persona_switch_command(user_text)
        effective_persona_id = switched or persona_id
        persona = get_persona(effective_persona_id)

        lang = detect_language(user_text)
        style = analyze_style(user_text)

        if not conversation_id or not self.memory.get_conversation(conversation_id):
            conv = self.memory.create_conversation(
                title=user_text[:60] or "New Conversation",
                language=lang.code,
                persona=effective_persona_id,
            )
            conversation_id = conv["id"]
        else:
            self.memory.update_conversation(
                conversation_id,
                language=lang.code,
                persona=effective_persona_id,
            )

        self.memory.add_message(
            conversation_id=conversation_id,
            role="user",
            content=user_text,
            language=lang.code,
            metadata={"persona": effective_persona_id, "tone": style.tone},
        )
        self.memory.set_preference("preferred_language", lang.code, category="communication")
        self.memory.set_preference("active_persona", effective_persona_id, category="communication")

        history = self.memory.get_messages(conversation_id, limit=20)
        chat_messages = [
            ChatMessage(role=m["role"], content=m["content"])
            for m in history
        ]

        prefs = self.memory.list_preferences()
        hints = [f"{p['key']}: {p['value']}" for p in prefs if p["category"] in {"communication", "coding", "projects"}]

        sys_prompt = build_system_instruction(
            persona=persona,
            language=lang,
            style=style,
            language_override=language_override,
            memory_hints=hints,
            user_text=user_text,
        )
        req = ChatRequest(
            messages=chat_messages,
            system_instruction=sys_prompt,
            model=model,
            temperature=persona.default_temperature,
        )
        style_summary = f"{style.tone} • {style.verbosity} • {style.emotion_cue}"
        return PreparedTurn(
            conversation_id=conversation_id,
            persona_id=effective_persona_id,
            switched_persona=switched,
            language=lang,
            style_summary=style_summary,
            chat_request=req,
        )

    async def send_message(
        self,
        user_text: str,
        conversation_id: str | None = None,
        persona_id: str = "professional",
        provider_id: str = "auto",
        language_override: str = "auto",
        model: str | None = None,
    ) -> dict[str, Any]:
        """Execute a complete non-streaming chat turn and persist assistant reply."""
        turn = self.prepare_turn(
            user_text=user_text,
            conversation_id=conversation_id,
            persona_id=persona_id,
            language_override=language_override,
            model=model,
        )
        allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
        resp: ChatResponse = await self.providers.generate(
            turn.chat_request,
            provider_id=provider_id,
            allow_cloud=allow_cloud,
        )
        saved = self.memory.add_message(
            conversation_id=turn.conversation_id,
            role="assistant",
            content=resp.text,
            language=turn.language.code,
            metadata={"provider": resp.provider, "model": resp.model},
        )
        self.audit_logger.log(
            category="chat",
            action=f"Chat turn completed ({resp.provider}/{resp.model})",
            permission="NETWORK" if allow_cloud else "READ",
            decision="completed",
            status="ok",
            details={"language": turn.language.code, "persona": turn.persona_id},
        )
        return {
            "conversation_id": turn.conversation_id,
            "message": saved,
            "persona": turn.persona_id,
            "switched_persona": turn.switched_persona,
            "detected_language": {
                "code": turn.language.code,
                "label": turn.language.label,
                "script": turn.language.script,
                "is_code_switched": turn.language.is_code_switched,
            },
            "style": turn.style_summary,
            "provider": resp.provider,
            "model": resp.model,
            "usage": {
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "latency_ms": round(resp.latency_ms, 1),
            },
        }

    async def stream_message(
        self,
        user_text: str,
        conversation_id: str | None = None,
        persona_id: str = "professional",
        provider_id: str = "auto",
        language_override: str = "auto",
        model: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream SSE-friendly events for a chat turn and persist final reply."""
        turn = self.prepare_turn(
            user_text=user_text,
            conversation_id=conversation_id,
            persona_id=persona_id,
            language_override=language_override,
            model=model,
        )
        yield {
            "event": "meta",
            "conversation_id": turn.conversation_id,
            "persona": turn.persona_id,
            "switched_persona": turn.switched_persona,
            "detected_language": {
                "code": turn.language.code,
                "label": turn.language.label,
                "script": turn.language.script,
            },
            "style": turn.style_summary,
        }

        allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
        chunks: list[str] = []
        used_provider = provider_id
        used_model = model or ""
        async for chunk in self.providers.stream(
            turn.chat_request,
            provider_id=provider_id,
            allow_cloud=allow_cloud,
        ):
            if chunk.provider:
                used_provider = chunk.provider
            if chunk.model:
                used_model = chunk.model
            if chunk.delta_text:
                chunks.append(chunk.delta_text)
                yield {"event": "delta", "text": chunk.delta_text}

        full_text = "".join(chunks)
        saved = self.memory.add_message(
            conversation_id=turn.conversation_id,
            role="assistant",
            content=full_text,
            language=turn.language.code,
            metadata={"provider": used_provider, "model": used_model},
        )
        yield {
            "event": "done",
            "conversation_id": turn.conversation_id,
            "message": saved,
            "provider": used_provider,
            "model": used_model,
        }
