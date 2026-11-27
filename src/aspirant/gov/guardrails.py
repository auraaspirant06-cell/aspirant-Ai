"""Hard security and legal guardrails for Indian Government Online Services."""

from __future__ import annotations

from typing import Any

from aspirant.gov.portal_registry import is_official_indian_gov_domain
from aspirant.security.command_policy import ApprovalQueue
from aspirant.security.redactor import contains_sensitive_secret, redact_sensitive_content


class GovGuardrailError(PermissionError):
    """Raised when an operation violates government verification, privacy, or approval rules."""


HARD_BLOCKED_ACTIONS = frozenset(
    {
        "bypass_captcha",
        "solve_captcha",
        "auto_otp",
        "read_otp",
        "biometric_spoof",
        "impersonate",
    }
)


def enforce_gov_guardrail(
    action: str,
    url: str | None = None,
    approvals: ApprovalQueue | None = None,
    approval_id: str | None = None,
    summary_target: str = "",
) -> dict[str, Any] | None:
    """Enforce mandatory blocks on CAPTCHA/OTP/biometrics/impersonation and approval gates on submit/pay."""
    norm = action.strip().lower()
    if norm in HARD_BLOCKED_ACTIONS:
        raise GovGuardrailError(
            f"Action '{action}' is strictly prohibited: CAPTCHA, OTP, biometric verification, "
            "and identity checks must be performed directly by the user."
        )

    if url is not None and not is_official_indian_gov_domain(url):
        raise GovGuardrailError(
            f"Blocked non-official URL {url!r}: only HTTPS .gov.in and .nic.in portals are permitted for automated assistance."
        )

    if norm in {"submit_application", "make_payment"}:
        if approvals is None:
            raise GovGuardrailError(f"Action '{action}' requires explicit approval workflow.")
        if not approval_id:
            req = approvals.request(
                category="gov",
                action=norm,
                target=summary_target or (url or norm),
                reason="Submitting a government application or making a payment requires your final explicit approval.",
                rollback_hint="Review every form field before clicking Approve; payments/submissions may be irreversible.",
            )
            return {"status": "approval_required", "approval": req.to_dict()}
        consumed = approvals.consume_approved(approval_id, expected_action=norm)
        if consumed is None:
            raise GovGuardrailError(f"Valid matching approval_id is required before '{action}'.")

    return None


def sanitize_transient_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Strip Aadhaar, PAN, OTPs, and passwords so they never enter persistent memory or logs."""
    blocked_keys = ("aadhaar", "aadhar", "pan", "otp", "password", "passcode", "pin_secret", "cvv")
    cleaned: dict[str, Any] = {}
    for k, v in fields.items():
        if any(tok in k.lower() for tok in blocked_keys):
            cleaned[k] = "[TRANSIENT_OMITTED]"
        elif isinstance(v, str) and contains_sensitive_secret(v):
            cleaned[k] = redact_sensitive_content(v).text
        else:
            cleaned[k] = v
    return cleaned
