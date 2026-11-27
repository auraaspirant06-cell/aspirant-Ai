"""Export OpenAPI 3.1 specification and standalone JSON Schemas from FastAPI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app  # noqa: E402
from backend.app.api.v1 import agents, auth, integrations, memory, voice  # noqa: E402


SCHEMA_DIR = ROOT / "docs" / "schemas"
OPENAPI_FILE = ROOT / "docs" / "openapi" / "aspirant-ecosystem-openapi.json"


def export_all() -> dict[str, int]:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    OPENAPI_FILE.parent.mkdir(parents=True, exist_ok=True)

    spec = app.openapi()
    OPENAPI_FILE.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    models: dict[str, type[BaseModel]] = {
        "register_request": auth.RegisterRequest,
        "remember_request": memory.RememberRequest,
        "agent_execute_request": agents.AgentExecuteRequest,
        "deep_reason_request": agents.DeepReasonRequest,
        "feedback_request": agents.FeedbackRequest,
        "voice_process_request": voice.VoiceProcessRequest,
        "voice_enroll_request": voice.VoiceEnrollRequest,
        "social_connect_request": integrations.ConnectSocialRequest,
        "social_dispatch_request": integrations.DispatchSocialRequest,
    }
    for name, model in models.items():
        schema_path = SCHEMA_DIR / f"{name}.schema.json"
        schema_path.write_text(
            json.dumps(model.model_json_schema(), indent=2),
            encoding="utf-8",
        )
    return {
        "openapi_paths": len(spec.get("paths", {})),
        "json_schemas": len(models),
    }


if __name__ == "__main__":
    summary = export_all()
    print(json.dumps(summary, indent=2))
