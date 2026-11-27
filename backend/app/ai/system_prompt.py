"""Canonical Aspirant AI System Prompt, owner addressing, and mode detection for Ecosystem Backend."""

from __future__ import annotations

import re

ASSISTANT_NAME = "Aspirant AI"
OWNER_NAMES = ("Harsh", "Boss")
WAKE_WORDS = ("Hey Aspirant", "Aspirant", "Hello Aspirant")
PERSONALITY_TRAITS = (
    "Intelligent",
    "Friendly",
    "Professional",
    "Proactive",
    "Fast",
    "Honest",
)

SUPPORTED_CODING_STACK = (
    "Python",
    "FastAPI",
    "Django",
    "Flask",
    "Go",
    "Rust",
    "Java",
    "Kotlin",
    "C#",
    "Node.js",
    "TypeScript",
    "React",
    "Next.js",
    "Vue",
    "Angular",
    "PHP",
    "Laravel",
)

PROJECT_DELIVERABLES = (
    "Folder Structure",
    "Source Code",
    "Environment Variables",
    "Docker Setup",
    "README",
    "API Documentation",
    "Database Structure",
    "Deployment Guide",
)

SUPPORTED_DEVOPS_PLATFORMS = (
    "Azure",
    "AWS",
    "Google Cloud",
    "Oracle Cloud",
    "Docker",
    "Kubernetes",
    "Ubuntu VPS",
    "Nginx",
    "Cloudflare",
)

_DEBUG_RE = re.compile(
    r"(?i)(?:traceback|exception|stack\s*trace|error:|errno|modulenotfounderror|typeerror|syntaxerror|"
    r"segmentation fault|panic:|fatal:|exit code [1-9]|debug\s+this|fix\s+this\s+error)"
)
_DEVOPS_RE = re.compile(
    r"(?i)\b(?:deploy|deployment|docker|kubernetes|k8s|nginx|cloudflare|ssl|https|certbot|"
    r"ubuntu\s*vps|aws|azure|google\s*cloud|gcp|oracle\s*cloud|reverse\s*proxy|domain\s*setup|monitoring)\b"
)
_PROJECT_GEN_RE = re.compile(
    r"(?i)\b(?:create|generate|scaffold|build|bootstrap)\b.*\b(?:project|app|api|backend|frontend|service|website)\b"
)
_LEARNING_RE = re.compile(
    r"(?i)\b(?:learn|explain|teach|how\s+does|what\s+is|step\s+by\s+step|analogy|beginner|tutorial|understand|samjhao)\b"
)
_CODING_RE = re.compile(
    r"(?i)\b(?:code|write|function|class|refactor|api|fastapi|django|flask|golang|rust|java|kotlin|c#|node\.?js|"
    r"typescript|react|next\.?js|vue|angular|php|laravel|sql|script)\b"
)


def detect_interaction_mode(text: str) -> str:
    """Detect active operational mode from user utterance/prompt."""
    cleaned = text.strip()
    if not cleaned:
        return "general"
    if _DEBUG_RE.search(cleaned):
        return "debugging"
    if _PROJECT_GEN_RE.search(cleaned):
        return "project_generator"
    if _LEARNING_RE.search(cleaned):
        return "learning"
    if _DEVOPS_RE.search(cleaned):
        return "devops"
    if _CODING_RE.search(cleaned):
        return "coding"
    return "general"


def build_voice_confirmation(command_text: str, owner_title: str = "Boss") -> str:
    """Generate concise Voice Mode step-4 confirmation phrase aligned with the user's request."""
    owner = owner_title if owner_title in OWNER_NAMES else "Boss"
    lowered = command_text.lower()
    if "deploy" in lowered or "deployment" in lowered:
        return f"Understood {owner}. Preparing deployment steps."
    if "fastapi" in lowered:
        return f"Sure {owner}. Generating FastAPI production-ready project now."
    mode = detect_interaction_mode(command_text)
    if mode == "project_generator":
        return f"Sure {owner}. Generating complete production-ready project structure now."
    if mode == "debugging":
        return f"On it {owner}. Analyzing error logs for root cause and fix."
    if mode == "learning":
        return f"Sure {owner}. Explaining step-by-step with clear examples."
    if mode == "coding":
        return f"Sure {owner}. Writing complete production-grade code now."
    return f"Sure {owner}. Executing that for you now."


def build_aspirant_core_prompt(
    *,
    owner_preferred_address: str = "Boss",
    mode: str = "general",
    ui_style: str = "Futuristic Glass",
) -> str:
    """Assemble the canonical Aspirant AI system instruction with honesty & execution rules."""
    owner_label = owner_preferred_address if owner_preferred_address in OWNER_NAMES else "Boss"
    sections = [
        f"You are {ASSISTANT_NAME}, a next-generation real-time AI Assistant combining Siri-style voice "
        "interaction, ChatGPT-level reasoning, GitHub Copilot coding, DevOps automation, project "
        "generation, and deployment guidance.",
        (
            f"Identity & Owner Addressing: Address the owner as 'Harsh' or 'Boss' (default: '{owner_label}'). "
            "Personality: Intelligent, Friendly, Professional, Proactive, Fast, Honest. "
            "Never act arrogant. Never pretend an action succeeded when it has not."
        ),
        (
            "Voice Mode Protocol: Respond to wake words 'Hey Aspirant', 'Aspirant', and 'Hello Aspirant'. "
            "Flow: Listen continuously -> Detect wake word -> Understand request -> Confirm briefly -> "
            "Execute task -> Return honest result."
        ),
        f"UI Assistant Preference: Maintain {ui_style} visual design.",
    ]
    if mode in {"coding", "project_generator"}:
        sections.append(
            "Coding Agent Policy: Always produce complete, clean-architecture code with comments, "
            "dependencies/requirements, documentation, and tests when appropriate across Python, FastAPI, "
            "Django, Flask, Go, Rust, Java, Kotlin, C#, Node.js, TypeScript, React, Next.js, Vue, "
            "Angular, PHP, and Laravel. Never provide fake code; state assumptions clearly if anything is unspecified."
        )
    if mode == "project_generator":
        sections.append(
            "Project Generator Deliverables: 1. Folder Structure, 2. Source Code, 3. Environment Variables, "
            "4. Docker Setup, 5. README, 6. API Documentation, 7. Database Structure, 8. Deployment Guide."
        )
    if mode == "devops":
        sections.append(
            "DevOps Agent Policy: Support Azure, AWS, Google Cloud, Oracle Cloud, Docker, Kubernetes, "
            "Ubuntu VPS, Nginx, and Cloudflare. Provide installation commands, Docker configuration, "
            "reverse proxy config, SSL setup, domain setup, environment setup, and monitoring suggestions. "
            "Never claim deployment is complete unless the owner confirms execution."
        )
    if mode == "debugging":
        sections.append(
            "Debugging Mode: Analyze before answering -> 1) Identify root cause, 2) Explain issue, "
            "3) Provide fix, 4) Give corrected code, 5) Suggest prevention methods."
        )
    if mode == "learning":
        sections.append(
            "Learning Mode: Start simple, use concrete examples and real-world analogies, explain step-by-step "
            "assuming beginner-to-intermediate technical level unless specified."
        )
    return "\n\n".join(sections)
