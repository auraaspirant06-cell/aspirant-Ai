"""FastAPI application factory, security middleware, and container state."""

from __future__ import annotations

from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
import secrets
import time
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from aspirant import APP_NAME, __version__
from aspirant.automation.app_launcher import AppLauncher
from aspirant.automation.browser_agent import IsolatedBrowserAgent
from aspirant.automation.file_ops import FileManagerEngine
from aspirant.automation.input_control import DesktopInputController
from aspirant.automation.screen_vision import ScreenVisionEngine
from aspirant.automation.terminal_runner import TerminalRunner
from aspirant.coding.autonomous import AutonomousCoder
from aspirant.coding.explainer import CodeExplainer
from aspirant.coding.generator import ProjectGenerator
from aspirant.coding.git_ops import GitCodeManager
from aspirant.coding.indexer import ProjectIndexer
from aspirant.coding.sandbox import CodingSandbox
from aspirant.core.chat_service import ChatService
from aspirant.core.config import AppSettings
from aspirant.core.events import EventBus
from aspirant.core.telemetry import TelemetryCollector
from aspirant.gov.form_assistant import GovServicesAssistant
from aspirant.media.image_studio import ImageStudio
from aspirant.media.video_studio import VideoStudio
from aspirant.memory.database import DatabaseInitializer
from aspirant.memory.store import MemoryStore
from aspirant.providers.registry import ProviderRegistry
from aspirant.providers.stt_providers import STTRouter
from aspirant.providers.tts_providers import TTSRouter
from aspirant.providers.usage import UsageTracker
from aspirant.security.audit import AuditLogger
from aspirant.security.auth import LocalAuthManager
from aspirant.security.command_policy import ApprovalQueue
from aspirant.security.permissions import PermissionManager
from aspirant.security.tokens import (
    is_allowed_host,
    is_allowed_origin,
    load_or_create_api_token,
)
from aspirant.security.vault import SecretVault
from aspirant.voice.pipeline import VoiceAssistantEngine


@dataclass
class AppContainer:
    """Shared runtime services attached to FastAPI app.state."""

    settings: AppSettings
    event_bus: EventBus
    telemetry: TelemetryCollector
    audit_logger: AuditLogger
    permissions: PermissionManager
    vault: SecretVault
    memory: MemoryStore
    usage_tracker: UsageTracker
    providers: ProviderRegistry
    chat: ChatService
    tts_router: TTSRouter
    stt_router: STTRouter
    voice: VoiceAssistantEngine
    approvals: ApprovalQueue
    apps: AppLauncher
    files: FileManagerEngine
    screen: ScreenVisionEngine
    terminal: TerminalRunner
    desktop_input: DesktopInputController
    browser_agent: IsolatedBrowserAgent
    coding_indexer: ProjectIndexer
    coding_generator: ProjectGenerator
    coding_sandbox: CodingSandbox
    coding_explainer: CodeExplainer
    git_mgr: GitCodeManager
    autonomous_coder: AutonomousCoder
    gov_assistant: GovServicesAssistant
    image_studio: ImageStudio
    video_studio: VideoStudio
    local_auth: LocalAuthManager
    api_token: str
    active_task: str = "Idle — Ready"


class SlidingWindowRateLimiter:
    """Simple per-client IP sliding window limiter for local control endpoints."""

    def __init__(self, max_requests: int = 180, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, client_id: str) -> bool:
        now = time.monotonic()
        bucket = self._hits[client_id]
        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            return False
        bucket.append(now)
        return True


def build_container(settings: AppSettings | None = None) -> AppContainer:
    """Create and initialize all core services cleanly."""
    cfg = settings or AppSettings()
    cfg.ensure_directories()

    db_init = DatabaseInitializer(cfg.memory_db_path, cfg.audit_db_path)
    db_init.initialize()

    event_bus = EventBus()
    audit_logger = AuditLogger(cfg.audit_db_path, event_bus=event_bus)
    permissions = PermissionManager(
        audit_db_path=cfg.audit_db_path,
        audit_logger=audit_logger,
        event_bus=event_bus,
        initial_restricted_mode=cfg.restricted_mode,
    )
    telemetry = TelemetryCollector(drive_root="C:\\")
    vault = SecretVault(cfg.vault_path)
    memory = MemoryStore(cfg.memory_db_path)
    usage_tracker = UsageTracker(cfg.memory_db_path)
    providers = ProviderRegistry(settings=cfg, vault=vault, usage_tracker=usage_tracker)
    chat = ChatService(
        memory=memory,
        providers=providers,
        permissions=permissions,
        audit_logger=audit_logger,
    )
    gemini_key = vault.get_secret("GEMINI_API_KEY") or cfg.gemini_api_key
    openai_key = vault.get_secret("OPENAI_API_KEY") or cfg.openai_api_key
    openai_url = vault.get_secret("OPENAI_BASE_URL") or cfg.openai_base_url
    groq_key = vault.get_secret("GROQ_API_KEY") or cfg.groq_api_key
    tts_router = TTSRouter(gemini_api_key=gemini_key)
    stt_router = STTRouter(
        gemini_key=gemini_key,
        openai_key=openai_key,
        openai_url=openai_url,
        groq_key=groq_key,
        whisper_model=cfg.whisper_model,
    )
    voice = VoiceAssistantEngine(
        chat_service=chat,
        tts_router=tts_router,
        stt_router=stt_router,
        permissions=permissions,
        audit_logger=audit_logger,
        event_bus=event_bus,
    )
    approvals = ApprovalQueue()
    apps = AppLauncher(permissions=permissions, audit_logger=audit_logger)
    files = FileManagerEngine(
        data_dir=cfg.resolved_data_dir,
        permissions=permissions,
        audit_logger=audit_logger,
    )
    screen = ScreenVisionEngine(
        outputs_dir=cfg.outputs_dir,
        permissions=permissions,
        audit_logger=audit_logger,
    )
    terminal = TerminalRunner(
        permissions=permissions,
        audit_logger=audit_logger,
        approvals=approvals,
    )
    desktop_input = DesktopInputController(
        permissions=permissions,
        audit_logger=audit_logger,
        approvals=approvals,
    )
    browser_agent = IsolatedBrowserAgent(
        profile_dir=cfg.browser_profile_dir,
        permissions=permissions,
        audit_logger=audit_logger,
    )
    coding_indexer = ProjectIndexer()
    coding_generator = ProjectGenerator(
        providers=providers,
        permissions=permissions,
        audit_logger=audit_logger,
    )
    coding_sandbox = CodingSandbox(
        permissions=permissions,
        audit_logger=audit_logger,
    )
    coding_explainer = CodeExplainer(
        providers=providers,
        permissions=permissions,
        indexer=coding_indexer,
    )
    git_mgr = GitCodeManager(
        permissions=permissions,
        audit_logger=audit_logger,
        approvals=approvals,
    )
    autonomous_coder = AutonomousCoder(
        indexer=coding_indexer,
        sandbox=coding_sandbox,
        git_mgr=git_mgr,
        providers=providers,
        permissions=permissions,
        audit_logger=audit_logger,
        approvals=approvals,
    )
    gov_assistant = GovServicesAssistant(
        providers=providers,
        permissions=permissions,
        audit_logger=audit_logger,
    )
    image_studio = ImageStudio(
        outputs_dir=cfg.outputs_dir,
        permissions=permissions,
        audit_logger=audit_logger,
    )
    video_studio = VideoStudio(
        outputs_dir=cfg.outputs_dir,
        providers=providers,
        tts_router=tts_router,
        permissions=permissions,
        audit_logger=audit_logger,
    )
    local_auth = LocalAuthManager(vault=vault)
    api_token = load_or_create_api_token(cfg.token_path)

    return AppContainer(
        settings=cfg,
        event_bus=event_bus,
        telemetry=telemetry,
        audit_logger=audit_logger,
        permissions=permissions,
        vault=vault,
        memory=memory,
        usage_tracker=usage_tracker,
        providers=providers,
        chat=chat,
        tts_router=tts_router,
        stt_router=stt_router,
        voice=voice,
        approvals=approvals,
        apps=apps,
        files=files,
        screen=screen,
        terminal=terminal,
        desktop_input=desktop_input,
        browser_agent=browser_agent,
        coding_indexer=coding_indexer,
        coding_generator=coding_generator,
        coding_sandbox=coding_sandbox,
        coding_explainer=coding_explainer,
        git_mgr=git_mgr,
        autonomous_coder=autonomous_coder,
        gov_assistant=gov_assistant,
        image_studio=image_studio,
        video_studio=video_studio,
        local_auth=local_auth,
        api_token=api_token,
    )


def require_bearer_auth(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Verify local API bearer token using constant-time comparison."""
    container: AppContainer = request.app.state.container
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer token.",
        )
    supplied = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(supplied, container.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized API token.",
        )


def create_app(
    settings: AppSettings | None = None,
    container: AppContainer | None = None,
) -> FastAPI:
    """Build the FastAPI server with auth, host/origin guards, and core routes."""
    runtime_container = container or build_container(settings)
    limiter = SlidingWindowRateLimiter()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        runtime_container.audit_logger.log(
            category="system",
            action="ASPIRANT AI core service started",
            permission="READ",
            decision="started",
            status="ok",
            details={"version": __version__, "host": runtime_container.settings.host},
        )
        yield
        runtime_container.voice.emergency_halt()
        await runtime_container.browser_agent.close_all()
        runtime_container.audit_logger.log(
            category="system",
            action="ASPIRANT AI core service stopped",
            permission="READ",
            decision="stopped",
            status="ok",
        )

    app = FastAPI(title=APP_NAME, version=__version__, lifespan=lifespan)
    app.state.container = runtime_container

    @app.middleware("http")
    async def security_guard_middleware(request: Request, call_next):
        if not is_allowed_host(request.headers.get("host")):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Forbidden Host header."},
            )
        if not is_allowed_origin(request.headers.get("origin")):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Cross-origin requests are blocked."},
            )
        client_host = request.client.host if request.client else "local"
        if not limiter.allow(client_host):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded."},
            )
        return await call_next(request)

    from aspirant.server.routes import register_routes
    from aspirant.server.routes_coding import create_coding_router
    from aspirant.server.routes_gov import create_gov_router
    from aspirant.server.routes_media import create_media_router
    from aspirant.server.routes_memory import create_memory_router

    auth_dep = Depends(require_bearer_auth)
    register_routes(app, auth_dependency=auth_dep)
    app.include_router(create_coding_router(runtime_container, auth_dependency=auth_dep))
    app.include_router(create_gov_router(runtime_container, auth_dependency=auth_dep))
    app.include_router(create_media_router(runtime_container, auth_dependency=auth_dep))
    app.include_router(create_memory_router(runtime_container, auth_dependency=auth_dep))
    return app
