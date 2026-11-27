# Phase 6 Report — Indian Government Services Assistant

## Completed & Verified Features

- **Official Portal Registry (`src/aspirant/gov/portal_registry.py`)**:
  - 19 verified HTTPS `.gov.in` / `.nic.in` service categories: Aadhaar, PAN, Voter ID, Passport, Income/Caste/Residence/Birth-Death Certificates, Ration Card, Labour Card, e-Shram, PM-KISAN, National Scholarship Portal, Govt Jobs (NCS), UPSC & SSC, RRB Railways, State e-District / DigiLocker / UMANG, Utility Bills, and MyScheme.
  - State e-District quick lookup across 16+ Indian states.
- **Hard Guardrails & Privacy (`src/aspirant/gov/guardrails.py`)**:
  - Enforces HTTPS `.gov.in` / `.nic.in` domain checks.
  - Permanently blocks CAPTCHA bypass/solving, OTP auto-reading, biometric spoofing, and impersonation.
  - Requires explicit `ApprovalQueue` confirmation before final application submission or payments.
  - Strips Aadhaar, PAN, OTP, and password patterns from transient document extraction and validation previews (`stored_in_memory: false`).
- **Desktop UI (`src/aspirant/ui/views/gov_view.py`)**: Interactive portal launcher, checklist viewer, form-field validator, transient document inspector, and scheme guidance box.
