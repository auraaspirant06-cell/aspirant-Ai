# Security Architecture & Responsible Use — ASPIRANT AI

## Core Guarantees
- **Loopback-Only Local Control Server**: Desktop server binds strictly to `127.0.0.1` with random per-session Bearer tokens stored under local user permissions.
- **Encrypted Secret Storage**: Provider keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, etc.) use Windows DPAPI / AES vault (`data/vault.enc`) or backend Fernet encryption-at-rest and are **never logged, returned in API responses, or stored in Git**.
- **Privacy-First Voice & Camera**: Microphone captures only on explicit activation (`Hey Baby`, Push-to-Talk, Continuous Mode) and shuts off cleanly on Mute or `Ctrl+Alt+Shift+E` Emergency Stop.
- **No Unconsented Biometrics or Memory Secret Retention**: Conversation memory filters out passwords, OTPs, PEM private keys, and API tokens automatically.

## Guarded Execution & Approval Gates
- **Command Policy Firewall**: Destructive disk/registry/security-tamper/encoded commands are blocked before execution.
- **Explicit Approval Queue**: Autonomous file edits, remote GitHub pushes, and cloud/VPS deployments (`Azure`, `AWS`, `Ubuntu VPS`, `DigitalOcean`, `Hetzner`) pause for owner approval (`confirmation_required=true`) before executing or marking complete.
- **Safe SSH/PEM Deployment Checks**: `verify_ssh_readiness()` checks key file existence and host validity without reading or displaying private key bytes.
- **No Anti-Bot / CAPTCHA / Credential Bypass**: Browser automation runs inside an isolated Playwright profile (`data/browser_profile`) with zero access to personal browser cookies and stops cleanly on logins/CAPTCHAs for manual user handling.
