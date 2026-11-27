export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  user: {
    id: string;
    email: string;
    full_name: string;
    role: string;
  };
}

export interface AgentRunResponse {
  run_id: string;
  objective: string;
  selected_agents: string[];
  plan_steps: Array<{ order: number; agent: string; output: string }>;
  final_output: string;
  status: string;
}

export interface VoicePipelineResponse {
  language: string;
  language_name: string;
  detected_intent: string;
  requires_authorization: boolean;
  confidence: number;
  speaker_verified: boolean;
  access_level: string;
  reply_text: string;
}

export interface SelfHealReport {
  overall_status: string;
  checks: Array<{ name: string; status: string; detail: string; repairable: boolean }>;
  repaired: string[];
}

async function requestJson<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export const ecosystemApi = {
  health: () =>
    requestJson<{
      status: string;
      vector_backend: string;
      cache_mode: string;
      products: string[];
    }>("/health"),
  register: (body: { email: string; password: string; full_name: string }) =>
    requestJson<AuthTokens>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  login: (body: { email: string; password: string }) =>
    requestJson<AuthTokens>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  executeAgents: (
    token: string,
    body: { objective: string; source_app: string; agents?: string[] }
  ) =>
    requestJson<AgentRunResponse>(
      "/agents/execute",
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  reasonDeep: (
    token: string,
    body: { objective: string; source_app?: string }
  ) =>
    requestJson<{
      intent: string;
      confidence: number;
      plan: string[];
      reflection: { passed: boolean; adjustments: string[] };
      final_answer: string;
    }>("/agents/reason", { method: "POST", body: JSON.stringify(body) }, token),
  novaClipboard: (token: string, content: string) =>
    requestJson<{ kind: string; suggested_actions: string[]; preview: string }>(
      "/nova/clipboard/analyze",
      { method: "POST", body: JSON.stringify({ content }) },
      token
    ),
  mjChat: (token: string, message: string) =>
    requestJson<{
      reply: string;
      provider: string;
      model: string;
      recalled_count: number;
    }>("/mj/chat", { method: "POST", body: JSON.stringify({ message }) }, token),
  maxDailyPlan: (token: string) =>
    requestJson<{
      date: string;
      focus_goals: Array<{ id: string; title: string; progress: number }>;
      habits: Array<{ id: string; title: string; streak: number }>;
      due_reminders: Array<{ id: string; title: string; due_at: string }>;
    }>("/max/daily-plan", { method: "GET" }, token),
  searchMemory: (token: string, q: string) =>
    requestJson<{
      query: string;
      results: Array<{ id: string; content: string; layer: string; score: number }>;
    }>(`/memory/search?q=${encodeURIComponent(q)}`, { method: "GET" }, token),
  voiceProcess: (
    token: string,
    body: {
      transcript: string;
      always_listening?: boolean;
      noise_db?: number;
      voice_samples?: number[];
    }
  ) =>
    requestJson<VoicePipelineResponse>(
      "/voice/process",
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  integrationsCatalog: (token: string) =>
    requestJson<{
      connectors: Array<{
        platform: string;
        display_name: string;
        connected: boolean;
        permissions: string[];
      }>;
    }>("/integrations/catalog", { method: "GET" }, token),
  selfHealAudit: (token: string, repair = false) =>
    requestJson<SelfHealReport>(
      repair ? "/self-healing/repair" : "/self-healing/audit",
      { method: repair ? "POST" : "GET" },
      token
    ),
};
