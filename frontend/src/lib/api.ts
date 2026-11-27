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
  health: () => requestJson<{ status: string; vector_backend: string; cache_mode: string; products: string[] }>("/health"),
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
  executeAgents: (token: string, body: { objective: string; source_app: string; agents?: string[] }) =>
    requestJson<AgentRunResponse>("/agents/execute", {
      method: "POST",
      body: JSON.stringify(body),
    }, token),
  novaVoice: (token: string, transcript: string) =>
    requestJson<{ run_id: string; response_text: string; selected_agents: string[] }>(
      "/nova/voice/command",
      { method: "POST", body: JSON.stringify({ transcript }) },
      token
    ),
  novaClipboard: (token: string, content: string) =>
    requestJson<{ kind: string; suggested_actions: string[]; preview: string }>(
      "/nova/clipboard/analyze",
      { method: "POST", body: JSON.stringify({ content }) },
      token
    ),
  mjChat: (token: string, message: string) =>
    requestJson<{ reply: string; provider: string; model: string; recalled_count: number }>(
      "/mj/chat",
      { method: "POST", body: JSON.stringify({ message }) },
      token
    ),
  mjResearchPlan: (token: string, topic: string) =>
    requestJson<{ run_id: string; goal_id: string; synthesis: string }>(
      "/mj/research/plan",
      { method: "POST", body: JSON.stringify({ topic, create_goal: true }) },
      token
    ),
  maxDailyPlan: (token: string) =>
    requestJson<{ date: string; focus_goals: Array<{ id: string; title: string; progress: number }>; habits: Array<{ id: string; title: string; streak: number }>; due_reminders: Array<{ id: string; title: string; due_at: string }> }>(
      "/max/daily-plan",
      { method: "GET" },
      token
    ),
  searchMemory: (token: string, q: string) =>
    requestJson<{ query: string; results: Array<{ id: string; content: string; layer: string; score: number }> }>(
      `/memory/search?q=${encodeURIComponent(q)}`,
      { method: "GET" },
      token
    ),
  storeMemory: (token: string, content: string, layer: string = "long_term") =>
    requestJson<{ id: string; summary: string }>(
      "/memory",
      { method: "POST", body: JSON.stringify({ content, layer, source_app: "web" }) },
      token
    ),
};
