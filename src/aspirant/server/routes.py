"""REST, SSE streaming, and WebSocket routes for ASPIRANT AI core."""

from __future__ import annotations

import asyncio
import json
import secrets
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from aspirant import APP_NAME, __version__
from aspirant.core.telemetry import invalidate_audio_cache
from aspirant.personality.language_detect import SUPPORTED_LANGUAGES
from aspirant.personality.personas import PERSONAS
from aspirant.providers.base import ProviderError
from aspirant.security.permissions import Permission, PermissionDeniedError
from aspirant.security.tokens import is_allowed_origin


class PermissionUpdateRequest(BaseModel):
    permission: Permission
    granted: bool


class RestrictedModeRequest(BaseModel):
    enabled: bool


class EmergencyStopRequest(BaseModel):
    reason: str = "User triggered Emergency STOP"


class ProviderConfigRequest(BaseModel):
    key_name: str
    value: str


class CreateConversationRequest(BaseModel):
    title: str = "New Conversation"
    language: str = "auto"
    persona: str = "professional"


class ChatSendRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    persona_id: str = "professional"
    provider_id: str = "auto"
    language_override: str = "auto"
    model: str | None = None


class VoiceConfigUpdateRequest(BaseModel):
    tts_provider: str | None = None
    stt_provider: str | None = None
    speed: float | None = None
    pitch_hz: int | None = None
    emotion: str | None = None
    noise_suppression: bool | None = None
    voice_override: str | None = None


class VoiceStartRequest(BaseModel):
    mode: str = "wake_word"


class VoiceSpeakRequest(BaseModel):
    text: str
    language_code: str = "auto"
    play_locally: bool = True


class VoiceTurnRequest(BaseModel):
    transcript: str
    provider_id: str = "auto"
    speak_output: bool = True


class VoiceChangeMicRequest(BaseModel):
    device_index: int


class VoiceTestMicRequest(BaseModel):
    device_index: int | None = None
    samples: list[float] | None = None


class VoiceMuteRequest(BaseModel):
    muted: bool


class ApprovalDecisionRequest(BaseModel):
    approve: bool


class AppOpenRequest(BaseModel):
    app_id: str
    args: list[str] = []


class TerminalRunRequest(BaseModel):
    command: str
    cwd: str | None = None
    approval_id: str | None = None
    timeout_sec: int = 30


class ScreenAnalyzeRequest(BaseModel):
    question: str = "Describe what is visible on the screen."
    image_path: str | None = None


class BrowserOpenRequest(BaseModel):
    url: str
    headless: bool = False


class FileWriteRequest(BaseModel):
    path: str
    content: str
    overwrite: bool = False


class FileMoveRequest(BaseModel):
    src: str
    dst: str


class FileOrganizeRequest(BaseModel):
    directory: str
    dry_run: bool = True


class FilePathRequest(BaseModel):
    path: str


def register_routes(app: FastAPI, auth_dependency: Any) -> None:
    """Attach REST, SSE, and WebSocket endpoints to the FastAPI app."""

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": APP_NAME, "version": __version__}

    @app.get("/api/v1/system/overview", dependencies=[auth_dependency])
    async def system_overview() -> dict[str, Any]:
        container = app.state.container
        return {
            "app": APP_NAME,
            "version": __version__,
            "active_task": container.active_task,
            "telemetry": container.telemetry.snapshot(),
            "security": container.permissions.snapshot(),
            "providers": container.providers.status_summary(),
            "voice": container.voice.status(),
            "ram_budget_mb": container.settings.ram_budget_mb,
            "data_dir": str(container.settings.resolved_data_dir),
        }

    @app.get("/api/v1/system/telemetry", dependencies=[auth_dependency])
    async def system_telemetry() -> dict[str, Any]:
        return app.state.container.telemetry.snapshot()

    @app.get("/api/v1/system/permissions", dependencies=[auth_dependency])
    async def get_permissions() -> dict[str, Any]:
        return app.state.container.permissions.snapshot()

    @app.post("/api/v1/system/permissions", dependencies=[auth_dependency])
    async def update_permission(body: PermissionUpdateRequest) -> dict[str, Any]:
        return app.state.container.permissions.set_permission(
            permission=body.permission, granted=body.granted, actor="ui"
        )

    @app.post("/api/v1/system/restricted-mode", dependencies=[auth_dependency])
    async def update_restricted_mode(body: RestrictedModeRequest) -> dict[str, Any]:
        return app.state.container.permissions.set_restricted_mode(
            enabled=body.enabled, actor="ui"
        )

    @app.post("/api/v1/system/emergency-stop", dependencies=[auth_dependency])
    async def emergency_stop(body: EmergencyStopRequest) -> dict[str, Any]:
        container = app.state.container
        container.active_task = "HALTED — Emergency STOP Active"
        return container.permissions.trigger_emergency_stop(reason=body.reason)

    @app.post("/api/v1/system/resume", dependencies=[auth_dependency])
    async def resume_system() -> dict[str, Any]:
        container = app.state.container
        state = container.permissions.resume_from_emergency_stop(actor="ui")
        container.active_task = "Idle — Ready"
        return state

    @app.get("/api/v1/audit/logs", dependencies=[auth_dependency])
    async def get_audit_logs(
        limit: int = Query(default=50, ge=1, le=500),
        category: str | None = Query(default=None),
    ) -> dict[str, Any]:
        items = app.state.container.audit_logger.recent(limit=limit, category=category)
        return {"items": items, "count": len(items)}

    @app.get("/api/v1/providers/status", dependencies=[auth_dependency])
    async def provider_status() -> dict[str, Any]:
        return {"providers": app.state.container.providers.status_summary()}

    @app.get("/api/v1/providers/health", dependencies=[auth_dependency])
    async def provider_health() -> dict[str, Any]:
        container = app.state.container
        return {
            "health": await container.providers.health_check_all(),
            "usage": container.usage_tracker.summary(),
        }

    @app.get("/api/v1/providers/usage", dependencies=[auth_dependency])
    async def provider_usage() -> dict[str, Any]:
        return {"usage": app.state.container.usage_tracker.summary()}

    @app.post("/api/v1/providers/configure", dependencies=[auth_dependency])
    async def configure_provider(body: ProviderConfigRequest) -> dict[str, Any]:
        container = app.state.container
        try:
            container.providers.configure_secret(body.key_name, body.value)
            gkey = container.vault.get_secret("GEMINI_API_KEY") or container.settings.gemini_api_key
            okey = container.vault.get_secret("OPENAI_API_KEY") or container.settings.openai_api_key
            ourl = container.vault.get_secret("OPENAI_BASE_URL") or container.settings.openai_base_url
            grkey = container.vault.get_secret("GROQ_API_KEY") or container.settings.groq_api_key
            container.tts_router.update_gemini_key(gkey)
            container.stt_router.refresh_keys(gkey, okey, ourl, grkey)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        container.audit_logger.log(
            category="security",
            action=f"Updated encrypted credential for {body.key_name}",
            permission="WRITE",
            decision="updated",
            status="ok",
        )
        return {"providers": container.providers.status_summary()}

    @app.get("/api/v1/personality/modes", dependencies=[auth_dependency])
    async def personality_modes() -> dict[str, Any]:
        return {
            "personas": [
                {"id": p.id, "name": p.name, "tagline": p.tagline}
                for p in PERSONAS.values()
            ],
            "languages": [
                {"code": code, "label": label, "script": script}
                for code, (label, script) in SUPPORTED_LANGUAGES.items()
            ],
        }

    @app.get("/api/v1/chat/conversations", dependencies=[auth_dependency])
    async def list_conversations() -> dict[str, Any]:
        return {"items": app.state.container.memory.list_conversations(limit=50)}

    @app.post("/api/v1/chat/conversations", dependencies=[auth_dependency])
    async def create_conversation(body: CreateConversationRequest) -> dict[str, Any]:
        return app.state.container.memory.create_conversation(
            title=body.title, language=body.language, persona=body.persona
        )

    @app.get("/api/v1/chat/conversations/{conversation_id}", dependencies=[auth_dependency])
    async def get_conversation(conversation_id: str) -> dict[str, Any]:
        mem = app.state.container.memory
        conv = mem.get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return {"conversation": conv, "messages": mem.get_messages(conversation_id, limit=200)}

    @app.delete("/api/v1/chat/conversations/{conversation_id}", dependencies=[auth_dependency])
    async def delete_conversation(conversation_id: str) -> dict[str, Any]:
        deleted = app.state.container.memory.delete_conversation(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return {"deleted": True, "conversation_id": conversation_id}

    @app.post("/api/v1/chat/send", dependencies=[auth_dependency])
    async def send_chat(body: ChatSendRequest) -> dict[str, Any]:
        container = app.state.container
        if not body.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty.")
        try:
            container.active_task = "Chatting with ASPIRANT AI"
            return await container.chat.send_message(
                user_text=body.message,
                conversation_id=body.conversation_id,
                persona_id=body.persona_id,
                provider_id=body.provider_id,
                language_override=body.language_override,
                model=body.model,
            )
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ProviderError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        finally:
            if not container.permissions.is_emergency_stopped:
                container.active_task = "Idle — Ready"

    @app.post("/api/v1/chat/stream", dependencies=[auth_dependency])
    async def stream_chat(body: ChatSendRequest) -> StreamingResponse:
        container = app.state.container
        if not body.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty.")

        async def event_generator():
            container.active_task = "Streaming response..."
            try:
                async for item in container.chat.stream_message(
                    user_text=body.message,
                    conversation_id=body.conversation_id,
                    persona_id=body.persona_id,
                    provider_id=body.provider_id,
                    language_override=body.language_override,
                    model=body.model,
                ):
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            except (PermissionDeniedError, ProviderError) as exc:
                yield f"data: {json.dumps({'event': 'error', 'detail': str(exc)})}\n\n"
            finally:
                if not container.permissions.is_emergency_stopped:
                    container.active_task = "Idle — Ready"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/api/v1/voice/status", dependencies=[auth_dependency])
    async def voice_status() -> dict[str, Any]:
        return app.state.container.voice.status()

    @app.post("/api/v1/voice/mute", dependencies=[auth_dependency])
    async def voice_mute(body: VoiceMuteRequest) -> dict[str, Any]:
        return app.state.container.voice.set_muted(body.muted)

    @app.get("/api/v1/voice/diagnostics/devices", dependencies=[auth_dependency])
    async def voice_diagnostics_devices() -> dict[str, Any]:
        mgr = app.state.container.voice.diagnostics
        invalidate_audio_cache()
        return await asyncio.to_thread(mgr.discover)

    @app.post("/api/v1/voice/diagnostics/test-mic", dependencies=[auth_dependency])
    async def voice_diagnostics_test_mic(
        body: VoiceTestMicRequest | list[float] | None = Body(default=None),
    ) -> dict[str, Any]:
        mgr = app.state.container.voice.diagnostics
        dev_idx: int | None = None
        samples: list[float] | None = None
        if isinstance(body, list):
            samples = body or None
        elif isinstance(body, VoiceTestMicRequest):
            dev_idx = body.device_index
            samples = body.samples or None
        result = await asyncio.to_thread(
            mgr.test_microphone, device_index=dev_idx, samples=samples
        )
        invalidate_audio_cache()
        return result

    @app.post("/api/v1/voice/diagnostics/change-mic", dependencies=[auth_dependency])
    async def voice_diagnostics_change_mic(body: VoiceChangeMicRequest) -> dict[str, Any]:
        mgr = app.state.container.voice.diagnostics
        res = await asyncio.to_thread(mgr.change_microphone, body.device_index)
        invalidate_audio_cache()
        return res

    @app.post("/api/v1/voice/diagnostics/recover", dependencies=[auth_dependency])
    async def voice_diagnostics_recover() -> dict[str, Any]:
        mgr = app.state.container.voice.diagnostics
        res = await asyncio.to_thread(mgr.recover)
        invalidate_audio_cache()
        return res

    @app.post("/api/v1/voice/config", dependencies=[auth_dependency])
    async def voice_config(body: VoiceConfigUpdateRequest) -> dict[str, Any]:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        return app.state.container.voice.update_config(updates)

    @app.post("/api/v1/voice/start", dependencies=[auth_dependency])
    async def voice_start(body: VoiceStartRequest) -> dict[str, Any]:
        if body.mode not in {"push_to_talk", "wake_word", "hands_free", "gemini_live"}:
            raise HTTPException(status_code=400, detail="Invalid voice activation mode.")
        try:
            loop = asyncio.get_running_loop()
            if body.mode == "gemini_live":
                c = app.state.container
                gkey = c.vault.get_secret("GEMINI_API_KEY") or c.settings.gemini_api_key
                res = c.voice.gemini_live.start(api_key=gkey, loop=loop, female_voice="Kore")
                c.voice._set_state("listening")
                return {**c.voice.status(), **res}
            return app.state.container.voice.start_listening(body.mode, loop)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/voice/stop", dependencies=[auth_dependency])
    async def voice_stop() -> dict[str, Any]:
        return app.state.container.voice.stop_listening()

    @app.post("/api/v1/voice/interrupt", dependencies=[auth_dependency])
    async def voice_interrupt() -> dict[str, Any]:
        return app.state.container.voice.interrupt_speech()

    @app.post("/api/v1/voice/speak", dependencies=[auth_dependency])
    async def voice_speak(body: VoiceSpeakRequest) -> dict[str, Any]:
        container = app.state.container
        if not body.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty.")
        try:
            tts = await container.voice.synthesize_only(body.text, language_code=body.language_code)
            if body.play_locally:
                await asyncio.to_thread(container.voice.playback.play_audio_bytes, tts.audio_bytes)
            return {
                "provider": tts.provider,
                "voice": tts.voice_name,
                "mime_type": tts.mime_type,
                "bytes": len(tts.audio_bytes),
                "latency_ms": round(tts.latency_ms, 1),
            }
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/voice/turn", dependencies=[auth_dependency])
    async def voice_turn(body: VoiceTurnRequest) -> dict[str, Any]:
        container = app.state.container
        if not body.transcript.strip():
            raise HTTPException(status_code=400, detail="Transcript cannot be empty.")
        try:
            return await container.voice.process_spoken_text(
                transcript=body.transcript,
                provider_id=body.provider_id,
                speak_output=body.speak_output,
            )
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ProviderError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    # --- Approvals & PC Control Routes (Phase 4) ---
    @app.get("/api/v1/approvals", dependencies=[auth_dependency])
    async def list_approvals(status_filter: str | None = None) -> dict[str, Any]:
        return {"items": app.state.container.approvals.list_requests(status_filter=status_filter)}

    @app.post("/api/v1/approvals/{approval_id}", dependencies=[auth_dependency])
    async def decide_approval(approval_id: str, body: ApprovalDecisionRequest) -> dict[str, Any]:
        req = app.state.container.approvals.decide(approval_id, body.approve)
        if req is None:
            raise HTTPException(status_code=404, detail="Approval request not found.")
        app.state.container.audit_logger.log(
            category="security",
            action=f"{'Approved' if body.approve else 'Denied'} action '{req.action}': {req.target[:80]}",
            permission="EXECUTE",
            decision="approved" if body.approve else "denied",
            status="ok",
        )
        return req.to_dict()

    @app.get("/api/v1/pc/apps", dependencies=[auth_dependency])
    async def list_apps() -> dict[str, Any]:
        return {"apps": app.state.container.apps.catalog()}

    @app.post("/api/v1/pc/apps/open", dependencies=[auth_dependency])
    async def open_app(body: AppOpenRequest) -> dict[str, Any]:
        try:
            return app.state.container.apps.open_app(body.app_id, body.args)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/pc/settings/{page_id}", dependencies=[auth_dependency])
    async def open_settings_page(page_id: str) -> dict[str, Any]:
        try:
            return app.state.container.apps.open_settings_page(page_id)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/pc/screen/capture", dependencies=[auth_dependency])
    async def capture_screen() -> dict[str, Any]:
        try:
            return app.state.container.screen.capture()
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/pc/screen/analyze", dependencies=[auth_dependency])
    async def analyze_screen(body: ScreenAnalyzeRequest) -> dict[str, Any]:
        c = app.state.container
        gkey = c.vault.get_secret("GEMINI_API_KEY") or c.settings.gemini_api_key
        try:
            return await c.screen.understand_screen(body.question, gkey, body.image_path)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/pc/terminal/run", dependencies=[auth_dependency])
    async def run_terminal_command(body: TerminalRunRequest) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(
                app.state.container.terminal.run,
                body.command,
                body.cwd,
                body.approval_id,
                body.timeout_sec,
            )
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/api/v1/pc/browser/open", dependencies=[auth_dependency])
    async def browser_open(body: BrowserOpenRequest) -> dict[str, Any]:
        try:
            return await app.state.container.browser_agent.open_tab(body.url, headless=body.headless)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/pc/browser/tabs", dependencies=[auth_dependency])
    async def browser_tabs() -> dict[str, Any]:
        try:
            return {"tabs": await app.state.container.browser_agent.list_tabs()}
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.delete("/api/v1/pc/browser/tabs/{index}", dependencies=[auth_dependency])
    async def browser_close_tab(index: int) -> dict[str, Any]:
        try:
            return await app.state.container.browser_agent.close_tab(index)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except IndexError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # --- File Manager Routes (Phase 4) ---
    @app.get("/api/v1/files/list", dependencies=[auth_dependency])
    async def files_list(path: str) -> dict[str, Any]:
        try:
            return app.state.container.files.list_directory(path)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/files/search", dependencies=[auth_dependency])
    async def files_search(root: str, pattern: str) -> dict[str, Any]:
        try:
            return {"items": app.state.container.files.search_files(root, pattern)}
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/files/read", dependencies=[auth_dependency])
    async def files_read(path: str) -> dict[str, Any]:
        try:
            return app.state.container.files.read_text(path)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/files/write", dependencies=[auth_dependency])
    async def files_write(body: FileWriteRequest) -> dict[str, Any]:
        try:
            return app.state.container.files.write_text(body.path, body.content, overwrite=body.overwrite)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/files/move", dependencies=[auth_dependency])
    async def files_move(body: FileMoveRequest) -> dict[str, Any]:
        try:
            return app.state.container.files.rename_or_move(body.src, body.dst)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (FileNotFoundError, FileExistsError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/files/trash", dependencies=[auth_dependency])
    async def files_trash(body: FilePathRequest) -> dict[str, Any]:
        try:
            return app.state.container.files.trash_delete(body.path)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/files/organize", dependencies=[auth_dependency])
    async def files_organize(body: FileOrganizeRequest) -> dict[str, Any]:
        try:
            return app.state.container.files.organize_folder(body.directory, dry_run=body.dry_run)
        except (PermissionDeniedError, PermissionError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.websocket("/ws/events")
    async def events_websocket(websocket: WebSocket) -> None:
        if not is_allowed_origin(websocket.headers.get("origin")):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        container = app.state.container
        await websocket.accept()
        try:
            auth_header = websocket.headers.get("authorization", "")
            authorized = False
            if auth_header.startswith("Bearer "):
                candidate = auth_header.removeprefix("Bearer ").strip()
                authorized = secrets.compare_digest(candidate, container.api_token)
            if not authorized:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
                candidate = str(msg.get("token", ""))
                authorized = (
                    msg.get("type") == "auth"
                    and secrets.compare_digest(candidate, container.api_token)
                )
            if not authorized:
                await websocket.send_json({"type": "error", "detail": "Unauthorized"})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            await websocket.send_json(
                {
                    "type": "connected",
                    "security": container.permissions.snapshot(),
                    "telemetry": container.telemetry.snapshot(),
                }
            )
            sub_id, queue = container.event_bus.subscribe()
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=2.0)
                        await websocket.send_json(event.to_dict())
                    except asyncio.TimeoutError:
                        await websocket.send_json(
                            {
                                "type": "telemetry.tick",
                                "payload": {
                                    "telemetry": container.telemetry.snapshot(),
                                    "active_task": container.active_task,
                                    "security": container.permissions.snapshot(),
                                },
                            }
                        )
            finally:
                container.event_bus.unsubscribe(sub_id)
        except (WebSocketDisconnect, asyncio.TimeoutError, HTTPException):
            return
