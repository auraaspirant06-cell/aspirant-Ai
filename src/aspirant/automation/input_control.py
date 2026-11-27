"""Gated PyAutoGUI desktop mouse/keyboard automation with failsafe and approval checks."""

from __future__ import annotations

from typing import Any

import pyautogui

from aspirant.security.audit import AuditLogger
from aspirant.security.command_policy import ApprovalQueue
from aspirant.security.permissions import Permission, PermissionManager

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.12

_BLOCKED_HOTKEYS = frozenset({("ctrl", "alt", "delete"), ("alt", "f4")})


class DesktopInputController:
    """Explicitly gated mouse and keyboard interaction engine."""

    def __init__(
        self,
        permissions: PermissionManager,
        audit_logger: AuditLogger,
        approvals: ApprovalQueue,
    ) -> None:
        self.permissions = permissions
        self.audit_logger = audit_logger
        self.approvals = approvals

    def pointer_info(self) -> dict[str, Any]:
        self.permissions.require(Permission.READ, "Read screen size and pointer position", category="input")
        pos = pyautogui.position()
        size = pyautogui.size()
        return {"x": pos.x, "y": pos.y, "screen_width": size.width, "screen_height": size.height}

    def perform_action(
        self,
        action_type: str,
        params: dict[str, Any],
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        self.permissions.require(Permission.EXECUTE, f"Desktop input action: {action_type}", category="input")
        target_desc = f"{action_type} {params}"
        if not approval_id:
            req = self.approvals.request(
                category="input",
                action="desktop_input",
                target=target_desc,
                reason="Mouse/keyboard automation alters active desktop windows.",
                rollback_hint="Press Emergency STOP or move cursor to top-left corner to abort PyAutoGUI.",
            )
            return {"status": "approval_required", "approval": req.to_dict()}

        consumed = self.approvals.consume_approved(approval_id, expected_action="desktop_input")
        if consumed is None:
            raise PermissionError("Valid approval_id is required before GUI mouse/keyboard control.")

        if action_type == "click":
            x, y = int(params["x"]), int(params["y"])
            pyautogui.click(x=x, y=y, button=str(params.get("button", "left")))
        elif action_type == "type_text":
            text = str(params["text"])
            pyautogui.write(text, interval=0.02)
        elif action_type == "hotkey":
            keys = tuple(str(k).lower() for k in params.get("keys", []))
            if keys in _BLOCKED_HOTKEYS:
                raise PermissionError(f"Blocked sensitive hotkey: {keys}")
            pyautogui.hotkey(*keys)
        else:
            raise ValueError(f"Unsupported desktop action: {action_type}")

        self.audit_logger.log(
            category="input",
            action=f"Executed GUI action: {action_type}",
            permission="EXECUTE",
            decision="executed",
            status="ok",
        )
        return {"status": "completed", "action": action_type}
