"""Phase 6 tests for official .gov.in/.nic.in registry, hard guardrails, transient doc prep, and UI."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication

from aspirant.core.config import AppSettings
from aspirant.gov.portal_registry import GOV_SERVICES, is_official_indian_gov_domain
from aspirant.server.app import build_container, create_app
from aspirant.ui.views.gov_view import GovServicesView


def test_all_primary_portals_are_official_gov_or_nic_domains() -> None:
    assert len(GOV_SERVICES) == 19
    for svc in GOV_SERVICES.values():
        assert is_official_indian_gov_domain(svc.official_url), f"{svc.id} has non-gov primary URL {svc.official_url}"
    assert is_official_indian_gov_domain("https://fake-aadhaar-update.com/") is False
    assert is_official_indian_gov_domain("http://uidai.gov.in/") is False  # HTTPS required


def test_gov_guardrails_block_captcha_otp_and_unapproved_submit_payment(tmp_path: Path) -> None:
    settings = AppSettings(ASPIRANT_DATA_DIR=tmp_path / "data")
    container = build_container(settings)
    app = create_app(settings=settings, container=container)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {container.api_token}"}

    doc_file = tmp_path / "sample_form_notes.txt"
    doc_file.write_text(
        "Applicant: Asha Devi\nPIN: 800001\nAadhaar: 2345 6789 0123\nPAN: ABCDE1234F\n",
        encoding="utf-8",
    )

    with client:
        # 1. Hard blocks
        for action in ("bypass_captcha", "solve_captcha", "auto_otp", "biometric_spoof", "impersonate"):
            r = client.post("/api/v1/gov/guard-check", headers=headers, json={"action": action})
            assert r.status_code == 403

        # 2. Non-official domain blocked
        r_bad_url = client.post(
            "/api/v1/gov/open-portal",
            headers=headers,
            params={"url": "https://unofficial-agent-pan.example.com/"},
        )
        assert r_bad_url.status_code == 403

        # 3. Payment & submission require explicit approval
        r_sub = client.post(
            "/api/v1/gov/guard-check",
            headers=headers,
            json={"action": "submit_application", "url": "https://serviceonline.gov.in/", "summary_target": "Income Cert"},
        )
        assert r_sub.status_code == 200
        assert r_sub.json()["status"] == "approval_required"
        ap_id = r_sub.json()["approval"]["id"]
        client.post(f"/api/v1/approvals/{ap_id}", headers=headers, json={"approve": True})

        r_sub_ok = client.post(
            "/api/v1/gov/guard-check",
            headers=headers,
            json={"action": "submit_application", "url": "https://serviceonline.gov.in/", "approval_id": ap_id},
        )
        assert r_sub_ok.json()["status"] == "approved_to_proceed"

        # 4. Field validation & transient doc extraction never save Aadhaar/PAN
        val = client.post(
            "/api/v1/gov/validate-fields",
            headers=headers,
            json={
                "service_id": "eshram",
                "fields": {
                    "full_name": "Ramesh Kumar",
                    "occupation_nco": "Mason",
                    "education_level": "10th",
                    "bank_ifsc": "SBIN0001234",
                    "state": "Bihar",
                    "pincode": "800001",
                    "aadhaar_number": "2345 6789 0123",
                },
            },
        )
        assert val.status_code == 200
        assert val.json()["ready_to_review"] is True
        assert val.json()["sanitized_preview"]["aadhaar_number"] == "[TRANSIENT_OMITTED]"

        ext = client.post(
            "/api/v1/gov/extract-document",
            headers=headers,
            json={"file_path": str(doc_file)},
        )
        assert ext.status_code == 200
        assert "2345 6789 0123" not in ext.json()["summary"]
        assert "ABCDE1234F" not in ext.json()["summary"]
        assert ext.json()["stored_in_memory"] is False

        # 5. Offline guidance fallback works with verified official link
        res_guide = client.post(
            "/api/v1/gov/research",
            headers=headers,
            json={"service_id": "pm_kisan", "question": "Check PM Kisan eligibility"},
        )
        assert res_guide.status_code == 200
        assert "pmkisan.gov.in" in res_guide.json()["official_url"]

    qt = QApplication.instance() or QApplication([])
    ui = GovServicesView(api_client=None)  # type: ignore[arg-type]
    assert ui.service_combo.count() == 19
    qt.processEvents()
