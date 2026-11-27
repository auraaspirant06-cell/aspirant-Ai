"""Indian Government Online Services Assistant view with official links, checklists, and guardrails."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aspirant.gov.portal_registry import GOV_SERVICES, STATE_E_DISTRICT_PORTALS
from aspirant.ui.client import AspirantApiClient
from aspirant.ui.theme import PALETTE
from aspirant.ui.widgets.glass import GlassCard, SectionHeader, StatusPill


class GovServicesView(QWidget):
    """Guides users through Indian government portals, documents, and validated form prep."""

    def __init__(self, api_client: AspirantApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)

        self.header = SectionHeader(
            "Indian Government Online Services",
            "Verified .gov.in / .nic.in portals • Document checklists • Field prep • Zero CAPTCHA/OTP bypass",
            badge_text="OFFICIAL ONLY",
            tone="ok",
        )
        layout.addWidget(self.header)

        # Service Selector + State Portal Lookup
        top_card = GlassCard()
        row1 = QHBoxLayout()
        self.service_combo = QComboBox()
        for svc in GOV_SERVICES.values():
            self.service_combo.addItem(f"{svc.name} [{svc.category}]", svc.id)
        self.service_combo.currentIndexChanged.connect(self._on_service_changed)

        self.state_combo = QComboBox()
        for state_name in sorted(STATE_E_DISTRICT_PORTALS):
            self.state_combo.addItem(state_name.title(), state_name)

        open_portal_btn = QPushButton("Open Official Portal")
        open_portal_btn.setProperty("variant", "primary")
        open_portal_btn.clicked.connect(self._open_portal)

        state_btn = QPushButton("Open State e-District")
        state_btn.setProperty("variant", "ghost")
        state_btn.clicked.connect(self._open_state_portal)

        row1.addWidget(QLabel("Service:"))
        row1.addWidget(self.service_combo, 2)
        row1.addWidget(open_portal_btn)
        row1.addWidget(QLabel("State:"))
        row1.addWidget(self.state_combo, 1)
        row1.addWidget(state_btn)
        top_card.body_layout.addLayout(row1)

        self.portal_info_lbl = QLabel()
        self.portal_info_lbl.setWordWrap(True)
        self.portal_info_lbl.setStyleSheet(f"color: {PALETTE['text_secondary']};")
        top_card.body_layout.addWidget(self.portal_info_lbl)
        layout.addWidget(top_card)

        # Form Preparation Validator + Transient Document Inspection
        prep_card = GlassCard()
        p_hdr = QHBoxLayout()
        p_title = QLabel("Form Field Checker & Guidance (No Aadhaar/PAN/OTPs Stored)")
        p_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.status_pill = StatusPill("VERIFIED PORTALS", "info")
        p_hdr.addWidget(p_title)
        p_hdr.addStretch(1)
        p_hdr.addWidget(self.status_pill)
        prep_card.body_layout.addLayout(p_hdr)

        self.fields_input = QTextEdit()
        self.fields_input.setFixedHeight(105)
        self.fields_input.setStyleSheet(
            "QTextEdit { background: rgba(10, 14, 28, 0.88); color: #F8FAFC; font-family: Consolas, monospace; border-radius: 8px; padding: 8px; }"
        )
        prep_card.body_layout.addWidget(self.fields_input)

        row2 = QHBoxLayout()
        validate_btn = QPushButton("Validate Form Fields")
        validate_btn.setProperty("variant", "primary")
        validate_btn.clicked.connect(self._validate_fields)

        self.doc_path_input = QLineEdit()
        self.doc_path_input.setPlaceholderText("Optional local document path for transient extraction...")
        extract_btn = QPushButton("Inspect Document (Transient)")
        extract_btn.setProperty("variant", "ghost")
        extract_btn.clicked.connect(self._extract_doc)

        row2.addWidget(validate_btn)
        row2.addWidget(self.doc_path_input, 1)
        row2.addWidget(extract_btn)
        prep_card.body_layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Ask eligibility, status check, or scheme question (English/Hindi/Hinglish)...")
        ask_btn = QPushButton("Ask Gov Assistant")
        ask_btn.setProperty("variant", "ghost")
        ask_btn.clicked.connect(self._ask_guidance)
        row3.addWidget(self.question_input, 1)
        row3.addWidget(ask_btn)
        prep_card.body_layout.addLayout(row3)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setMinimumHeight(180)
        self.output_box.setStyleSheet(
            "QTextEdit { background: rgba(8, 12, 24, 0.92); color: #A5F3FC; font-family: Consolas, monospace; border-radius: 8px; padding: 8px; }"
        )
        prep_card.body_layout.addWidget(self.output_box)
        layout.addWidget(prep_card)

        guard_card = GlassCard(subtle=True)
        g_lbl = QLabel(
            "Strict Legal & Security Guardrails: CAPTCHA, OTP, biometrics, payments, and final form submission "
            "must ALWAYS be completed/approved by you directly. Aadhaar/PAN/OTPs are never saved to memory."
        )
        g_lbl.setWordWrap(True)
        g_lbl.setStyleSheet(f"color: {PALETTE['neon_cyan']}; font-size: 12px;")
        guard_card.body_layout.addWidget(g_lbl)
        layout.addWidget(guard_card)

        self._on_service_changed()

    def _current_service_id(self) -> str:
        return str(self.service_combo.currentData())

    def _on_service_changed(self) -> None:
        svc = GOV_SERVICES[self._current_service_id()]
        self.portal_info_lbl.setText(
            f"Official URL: {svc.official_url}\n"
            f"Required Documents: {', '.join(svc.required_documents)}\n"
            f"Eligibility: {svc.eligibility_summary}\n"
            f"Status Guide: {svc.status_check_guide}"
        )
        sample = {f: "" for f in svc.typical_form_fields}
        self.fields_input.setPlainText(json.dumps(sample, indent=2))

    def _open_portal(self) -> None:
        svc = GOV_SERVICES[self._current_service_id()]
        try:
            res = self.api_client._request("POST", "/api/v1/gov/open-portal", params={"url": svc.official_url})
            self.output_box.setPlainText(f"Opened verified portal in isolated Edge:\n{res}")
        except Exception as exc:
            self.output_box.setPlainText(f"Portal open requires BROWSER+NETWORK permissions: {exc}")

    def _open_state_portal(self) -> None:
        st = str(self.state_combo.currentData())
        try:
            info = self.api_client._request("GET", "/api/v1/gov/state-portal", params={"state": st})
            res = self.api_client._request("POST", "/api/v1/gov/open-portal", params={"url": info["official_url"]})
            self.output_box.setPlainText(f"Opened {st.title()} portal:\n{res}")
        except Exception as exc:
            self.output_box.setPlainText(f"State portal lookup/open: {exc}")

    def _validate_fields(self) -> None:
        try:
            fields = json.loads(self.fields_input.toPlainText() or "{}")
            res = self.api_client._request(
                "POST",
                "/api/v1/gov/validate-fields",
                json={"service_id": self._current_service_id(), "fields": fields},
            )
            self.status_pill.set_tone("ok" if res["ready_to_review"] else "warn", "READY" if res["ready_to_review"] else "INCOMPLETE")
            self.output_box.setPlainText(json.dumps(res, indent=2))
        except Exception as exc:
            self.status_pill.set_tone("danger", "INVALID")
            self.output_box.setPlainText(str(exc))

    def _extract_doc(self) -> None:
        path = self.doc_path_input.text().strip()
        if not path:
            return
        try:
            res = self.api_client._request("POST", "/api/v1/gov/extract-document", json={"file_path": path})
            self.output_box.setPlainText(json.dumps(res, indent=2, ensure_ascii=False))
        except Exception as exc:
            self.output_box.setPlainText(str(exc))

    def _ask_guidance(self) -> None:
        q = self.question_input.text().strip()
        if not q:
            return
        try:
            res = self.api_client._request(
                "POST",
                "/api/v1/gov/research",
                json={"service_id": self._current_service_id(), "question": q},
                timeout=40.0,
            )
            self.output_box.setPlainText(
                f"Official Portal: {res['official_url']}\nProvider: {res['provider']}\n\n{res['answer']}"
            )
        except Exception as exc:
            self.output_box.setPlainText(str(exc))
