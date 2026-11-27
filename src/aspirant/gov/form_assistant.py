"""Form-field validation, transient document extraction, and scheme research assistant."""

from __future__ import annotations

import base64
from pathlib import Path
import re
from typing import Any

from google import genai

from aspirant.gov.guardrails import sanitize_transient_fields
from aspirant.gov.portal_registry import GOV_SERVICES
from aspirant.providers.base import ChatMessage, ChatRequest
from aspirant.providers.registry import ProviderRegistry
from aspirant.security.audit import AuditLogger
from aspirant.security.command_policy import is_protected_path
from aspirant.security.permissions import Permission, PermissionManager
from aspirant.security.redactor import redact_sensitive_content

_PINCODE_RE = re.compile(r"^[1-9]\d{5}$")
_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_DOB_RE = re.compile(r"^(?:\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class GovServicesAssistant:
    """Prepares official government checklists, validates fields, and guides status/scheme queries."""

    def __init__(
        self,
        providers: ProviderRegistry,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
    ) -> None:
        self.providers = providers
        self.permissions = permissions
        self.audit_logger = audit_logger

    def validate_fields(self, service_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Validate form preparation fields in memory without storing sensitive IDs."""
        spec = GOV_SERVICES.get(service_id)
        if spec is None:
            raise ValueError(f"Unknown government service '{service_id}'.")

        errors: list[str] = []
        missing: list[str] = []

        for req_field in spec.typical_form_fields:
            val = str(fields.get(req_field, "")).strip()
            if not val:
                missing.append(req_field)

        if "pincode" in fields and str(fields["pincode"]).strip():
            if not _PINCODE_RE.match(str(fields["pincode"]).strip()):
                errors.append("pincode must be a valid 6-digit Indian PIN code.")
        if "ifsc_code" in fields and str(fields["ifsc_code"]).strip():
            if not _IFSC_RE.match(str(fields["ifsc_code"]).strip().upper()):
                errors.append("ifsc_code must follow standard 11-character RBI IFSC format (e.g. SBIN0001234).")
        if "dob" in fields and str(fields["dob"]).strip():
            if not _DOB_RE.match(str(fields["dob"]).strip()):
                errors.append("dob should be formatted as DD/MM/YYYY or YYYY-MM-DD.")
        if "email" in fields and str(fields["email"]).strip():
            if not _EMAIL_RE.match(str(fields["email"]).strip()):
                errors.append("email format appears invalid.")

        safe_preview = sanitize_transient_fields(fields)
        self.audit_logger.log(
            category="gov",
            action=f"Validated preparation fields for {spec.name}",
            permission="READ",
            decision="validated",
            status="ok" if not errors else "warn",
        )
        return {
            "service": spec.name,
            "official_url": spec.official_url,
            "ready_to_review": len(errors) == 0 and len(missing) == 0,
            "missing_fields": missing,
            "validation_errors": errors,
            "sanitized_preview": safe_preview,
        }

    async def extract_document_transient(
        self, file_path: str, gemini_api_key: str | None = None
    ) -> dict[str, Any]:
        """Read a local document transiently; strips Aadhaar/PAN/OTPs before logging or caching."""
        self.permissions.require(Permission.READ, "Inspect uploaded document for form prep", category="gov")
        target = Path(file_path).expanduser().resolve()
        blocked, reason = is_protected_path(target)
        if blocked:
            raise PermissionError(reason)
        if not target.is_file():
            raise FileNotFoundError(f"Document not found: {target}")

        suffix = target.suffix.lower()
        if suffix in {".txt", ".md", ".csv", ".json"}:
            raw = target.read_text(encoding="utf-8", errors="replace")[:8000]
            scrubbed = redact_sensitive_content(raw)
            self.audit_logger.log(
                category="gov",
                action=f"Transient text inspection on {target.name} (redacted={scrubbed.redacted_count})",
                permission="READ",
                decision="executed",
                status="ok",
            )
            return {
                "filename": target.name,
                "mode": "local_text",
                "summary": scrubbed.text[:2500],
                "redacted_sensitive_count": scrubbed.redacted_count,
                "stored_in_memory": False,
            }

        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            self.permissions.require(Permission.NETWORK, "Extract form fields via Gemini Vision", category="gov")
            if not gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is required for image document extraction.")
            b64 = base64.b64encode(target.read_bytes()).decode("ascii")
            mime = "image/png" if suffix == ".png" else ("image/webp" if suffix == ".webp" else "image/jpeg")
            client = genai.Client(api_key=gemini_api_key)
            resp = await client.aio.interactions.create(
                model="gemini-4-hydrogen",
                input=[
                    {
                        "type": "text",
                        "text": (
                            "Extract ONLY non-sensitive public form helper details (Applicant Name, Address, PIN code, District/State) "
                            "to assist filling a government form. Do NOT repeat Aadhaar numbers, PAN numbers, or OTPs."
                        ),
                    },
                    {"type": "image", "data": b64, "mime_type": mime},
                ],
                store=False,
            )
            text = getattr(resp, "output_text", None) or ""
            scrubbed = redact_sensitive_content(text)
            return {
                "filename": target.name,
                "mode": "vision_transient",
                "summary": scrubbed.text,
                "redacted_sensitive_count": scrubbed.redacted_count,
                "stored_in_memory": False,
            }

        return {
            "filename": target.name,
            "mode": "metadata_only",
            "summary": f"File '{target.name}' ({target.stat().st_size} bytes) ready for manual portal upload.",
            "stored_in_memory": False,
        }

    async def research_guidance(
        self,
        service_id: str,
        question: str,
        language_hint: str = "en",
        provider_id: str = "auto",
    ) -> dict[str, Any]:
        """Provide grounded guidance on official rules/eligibility without fabricating details."""
        self.permissions.require(Permission.READ, f"Research gov guidance for {service_id}", category="gov")
        spec = GOV_SERVICES.get(service_id)
        if spec is None:
            raise ValueError(f"Unknown service '{service_id}'.")

        # Never forward raw sensitive digits to external LLMs
        safe_q = redact_sensitive_content(question).text
        allow_cloud = self.permissions.is_allowed(Permission.NETWORK)
        try:
            resp = await self.providers.generate(
                ChatRequest(
                    messages=[
                        ChatMessage(
                            "user",
                            f"Service: {spec.name}\nOfficial Portal: {spec.official_url}\n"
                            f"Known Required Docs: {', '.join(spec.required_documents)}\n"
                            f"User Question ({language_hint}): {safe_q}\n"
                            "Answer clearly, direct the user only to official .gov.in/.nic.in portals, "
                            "and state clearly if latest fee/date must be checked on the official portal.",
                        )
                    ],
                    system_instruction=(
                        "You are ASPIRANT AI Indian Government Services Assistant. "
                        "Never fabricate government rules, deadlines, or fees."
                    ),
                    temperature=0.2,
                ),
                provider_id=provider_id,
                allow_cloud=allow_cloud,
            )
            return {
                "service": spec.name,
                "official_url": spec.official_url,
                "answer": resp.text,
                "provider": resp.provider,
            }
        except Exception:
            # Deterministic grounded offline fallback from official registry
            return {
                "service": spec.name,
                "official_url": spec.official_url,
                "answer": (
                    f"Official Portal: {spec.official_url}\n"
                    f"Eligibility: {spec.eligibility_summary}\n"
                    f"Required Documents: {', '.join(spec.required_documents)}\n"
                    f"Status Guide: {spec.status_check_guide}"
                ),
                "provider": "official-registry-offline",
            }
