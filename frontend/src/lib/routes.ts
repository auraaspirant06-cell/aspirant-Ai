export type RouteId =
  | "overview"
  | "nova"
  | "mj"
  | "max"
  | "voice"
  | "agents"
  | "memory"
  | "integrations"
  | "security"
  | "settings";

export interface AppRouteDefinition {
  id: RouteId;
  href: string;
  label: string;
  sublabel: string;
  screenTitle: string;
  componentName: string;
}

export const APP_ROUTES: readonly AppRouteDefinition[] = [
  {
    id: "overview",
    href: "/",
    label: "Ecosystem",
    sublabel: "Command Center",
    screenTitle: "Ecosystem Command Center",
    componentName: "OverviewScreen",
  },
  {
    id: "nova",
    href: "/nova",
    label: "NOVA",
    sublabel: "Windows Desktop",
    screenTitle: "NOVA Desktop Operator",
    componentName: "NovaScreen",
  },
  {
    id: "mj",
    href: "/mj",
    label: "MJ",
    sublabel: "Human Intelligence",
    screenTitle: "MJ Human Intelligence",
    componentName: "MjScreen",
  },
  {
    id: "max",
    href: "/max",
    label: "MAX",
    sublabel: "Mobile Companion",
    screenTitle: "MAX Mobile Companion",
    componentName: "MaxScreen",
  },
  {
    id: "voice",
    href: "/voice",
    label: "Voice & ID",
    sublabel: "13+ Indic & Speaker Auth",
    screenTitle: "Voice Intelligence & Identity",
    componentName: "VoiceScreen",
  },
  {
    id: "agents",
    href: "/agents",
    label: "7 Agents",
    sublabel: "Reasoning & Reflection",
    screenTitle: "Multi-Agent Reasoning Engine",
    componentName: "AgentsScreen",
  },
  {
    id: "memory",
    href: "/memory",
    label: "Memory & RAG",
    sublabel: "Qdrant + Chroma",
    screenTitle: "Semantic Memory & Hybrid RAG",
    componentName: "MemoryScreen",
  },
  {
    id: "integrations",
    href: "/integrations",
    label: "Integrations",
    sublabel: "Official Social APIs",
    screenTitle: "Social Platform Integrations",
    componentName: "IntegrationsScreen",
  },
  {
    id: "security",
    href: "/security",
    label: "Security",
    sublabel: "JWT, Audit & Self-Heal",
    screenTitle: "Zero-Trust Security & Self-Healing",
    componentName: "SecurityScreen",
  },
  {
    id: "settings",
    href: "/settings",
    label: "Settings",
    sublabel: "Voice, Theme & Providers",
    screenTitle: "Ecosystem Preferences & Settings",
    componentName: "SettingsScreen",
  },
] as const;

export function getRouteById(id: RouteId): AppRouteDefinition {
  const found = APP_ROUTES.find((r) => r.id === id);
  if (!found) {
    throw new Error(`Unknown route id: ${id}`);
  }
  return found;
}

export function normalizePathname(pathname: string): string {
  if (!pathname || pathname === "/") return "/";
  return pathname.replace(/\/+$/, "") || "/";
}

export function getRouteByPathname(pathname: string): AppRouteDefinition | undefined {
  const clean = normalizePathname(pathname);
  return APP_ROUTES.find((r) => r.href === clean);
}
