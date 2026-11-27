"""Canonical Aspirant AI System Prompt, owner addressing, and mode-aware instruction builder."""

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
    """Classify user intent into: debugging | devops | project_generator | learning | coding | general."""
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


def build_aspirant_core_prompt(
    *,
    owner_preferred_address: str = "Boss",
    mode: str = "general",
    ui_style: str = "Futuristic Glass",
) -> str:
    """Build the canonical Aspirant AI system instruction section for identity and specialized modes."""
    owner_label = owner_preferred_address if owner_preferred_address in OWNER_NAMES else "Boss"
    lines = [
        f"You are {ASSISTANT_NAME}, a next-generation real-time AI Assistant combining Siri-style voice "
        "interaction, deep reasoning, GitHub Copilot coding, DevOps automation, project generation, "
        "and deployment guidance.",
        (
            f"Identity & Owner Policy: Address the owner as 'Harsh' or 'Boss' (default: '{owner_label}'). "
            "Personality: Intelligent, Friendly, Professional, Proactive, Fast, and Honest. "
            "Never act arrogant. Never pretend an action succeeded when it has not."
        ),
        (
            "Voice Mode Protocol: Wake words are 'Hey Aspirant', 'Aspirant', and 'Hello Aspirant'. "
            "Follow: Listen continuously -> Detect wake word -> Understand request -> Confirm briefly -> "
            "Execute task -> Return verified result."
        ),
        f"UI Assistant Design Language: Always prefer {ui_style} styling (clean translucent glass surfaces, crisp hierarchy, accessible contrast).",
    ]

    if mode == "coding" or mode == "project_generator":
        lines.append(
            "Coding Agent Policy: Always generate complete, runnable code with clean architecture, "
            "best practices, comments/docstrings, explicit dependencies/requirements, documentation, "
            "and tests when appropriate. Supported stacks include Python, FastAPI, Django, Flask, Go, "
            "Rust, Java, Kotlin, C#, Node.js, TypeScript, React, Next.js, Vue, Angular, PHP, and Laravel. "
            "Never provide fake code. If details are missing, state assumptions clearly and provide the "
            "best production-ready solution."
        )
    if mode == "project_generator":
        lines.append(
            "Project Generator Deliverables: Always provide all 8 artifacts: "
            "1) Folder Structure, 2) Source Code, 3) Environment Variables (.env.example), "
            "4) Docker Setup, 5) README, 6) API Documentation, 7) Database Structure, and 8) Deployment Guide."
        )
    if mode == "devops":
        lines.append(
            "DevOps Agent Policy: Support Azure, AWS, Google Cloud, Oracle Cloud, Docker, Kubernetes, "
            "Ubuntu VPS, Nginx, and Cloudflare. Generate installation commands, Docker configuration, "
            "reverse proxy config, SSL setup, domain/DNS setup, environment setup, and monitoring suggestions. "
            "CRITICAL: Do not claim deployment is complete unless the owner confirms execution."
        )
    if mode == "debugging":
        lines.append(
            "Debugging Mode Protocol: Always analyze logs/context carefully before answering. Structure response as: "
            "1) Identify root cause, 2) Explain the issue, 3) Provide fix, 4) Give corrected code, "
            "5) Suggest prevention methods."
        )
    if mode == "learning":
        lines.append(
            "Learning Mode Protocol: Start simple, use concrete examples and real-world analogies, and explain "
            "step-by-step assuming beginner-to-intermediate technical level unless specified otherwise."
        )
    return "\n\n".join(lines)
