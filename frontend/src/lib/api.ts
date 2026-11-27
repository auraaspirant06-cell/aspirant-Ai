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
  remembered_language?: string;
}

export interface MicDeviceInfo {
  index: number;
  name: string;
  display_name?: string;
  device_type: string;
  hostapi?: string;
  default_samplerate: number;
  supported_sample_rates?: number[];
  driver_status: string;
  usable?: boolean;
  is_default: boolean;
  is_selected?: boolean;
}

export interface AudioDiagnosticsResponse {
  mic_available: boolean;
  mic_status?: string;
  permission?: {
    granted: boolean;
    status: string;
    detail: string;
    settings_uri?: string;
  };
  input_devices: MicDeviceInfo[];
  output_devices: Array<{ index: number; name: string; default_samplerate: number }>;
  best_device: MicDeviceInfo | null;
  active_device?: MicDeviceInfo | null;
  health_status: string;
  issues_detected: string[];
  repair_guidance: string[];
}

export interface MicTestResponse {
  rms_level: number;
  peak_level?: number;
  db_level?: number;
  volume_percent?: number;
  used_sample_rate?: number;
  signal_quality: "ok" | "quiet_ready" | "muted" | "clipping" | "unavailable" | "unknown";
  device_opened?: boolean;
  mic_available: boolean;
  best_device: { name: string; display_name?: string; device_type: string; default_samplerate?: number } | null;
  issues: string[];
  guidance: string[];
}

export interface VoiceStatusResponse {
  listening_mode: string;
  wake_word_armed: boolean;
  asr_status: string;
  vad_active: boolean;
  voice_activity_percent?: number;
  noise_suppression_on: boolean;
  muted?: boolean;
  mic_connected: boolean;
  mic_status?: string;
  current_device_index?: number | null;
  current_device_name: string;
  current_device_type: string;
  driver_status?: string;
  sample_rate?: number;
  health_status: string;
  issues: string[];
}

export interface MicRecoverResponse {
  status: "recovered" | "no_devices";
  mic_status?: string;
  device: MicDeviceInfo | null;
  steps_attempted?: string[];
  error?: string;
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
  novaWindowsList: (token: string) =>
    requestJson<{ platform: string; windows: Array<{ hwnd: number; title: string }> }>(
      "/nova/windows/list",
      { method: "GET" },
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
  smartMemoryProfile: (token: string) =>
    requestJson<{
      language_preference: string;
      frequent_actions: Record<string, number>;
      device_preferences: Record<string, unknown>;
    }>("/memory/profile/smart", { method: "GET" }, token),
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
  voicePresets: () =>
    requestJson<{
      presets: Array<{ id: string; name: string; accent: string; style: string; voice_id: string }>;
    }>("/voice/presets"),
  voiceAudioDiagnostics: (token: string) =>
    requestJson<AudioDiagnosticsResponse>(
      "/voice/diagnostics/audio",
      { method: "GET" },
      token
    ),
  voiceDiagnosticsDevices: (token: string) =>
    requestJson<AudioDiagnosticsResponse>("/voice/diagnostics/devices", { method: "GET" }, token),
  voiceTestMic: (token: string, body: { device_index?: number; samples?: number[] } = {}) =>
    requestJson<MicTestResponse>(
      "/voice/diagnostics/test-mic",
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  voiceChangeMic: (token: string, deviceIndex: number) =>
    requestJson<AudioDiagnosticsResponse & { status: string; active_device_name: string }>(
      "/voice/diagnostics/change-mic",
      { method: "POST", body: JSON.stringify({ device_index: deviceIndex }) },
      token
    ),
  voiceRecoverMic: (token: string) =>
    requestJson<MicRecoverResponse>("/voice/diagnostics/recover", { method: "POST" }, token),
  voiceMute: (token: string, muted: boolean) =>
    requestJson<VoiceStatusResponse>(
      "/voice/mute",
      { method: "POST", body: JSON.stringify({ muted }) },
      token
    ),
  voiceStatus: (token: string) =>
    requestJson<VoiceStatusResponse>("/voice/status", { method: "GET" }, token),
  generateProject: (
    token: string,
    body: { project_name: string; stack: string; description?: string }
  ) =>
    requestJson<{
      project_name: string;
      stack: string;
      deliverables: string[];
      folder_structure: string;
      environment_variables: string;
      docker_setup: string;
      api_documentation: string;
      database_structure: string;
      deployment_guide: string;
    }>("/agents/project/generate", { method: "POST", body: JSON.stringify(body) }, token),
  devopsPlan: (
    token: string,
    body: {
      app_name?: string;
      platform: string;
      domain?: string;
      app_port?: number;
      execution_confirmed?: boolean;
    }
  ) =>
    requestJson<{
      platform: string;
      status: string;
      confirmation_required: boolean;
      message: string;
      docker_configuration: string;
      reverse_proxy_configuration: string;
      ssl_setup: string;
      monitoring_suggestions: string[];
    }>("/agents/devops/plan", { method: "POST", body: JSON.stringify(body) }, token),
  debugLogs: (token: string, body: { error_log: string; code_context?: string }) =>
    requestJson<{
      root_cause: string;
      issue_explanation: string;
      fix: string;
      corrected_code: string;
      prevention_methods: string[];
    }>("/agents/debug", { method: "POST", body: JSON.stringify(body) }, token),
  learnConcept: (token: string, body: { concept: string; level?: string }) =>
    requestJson<{
      concept: string;
      simple_explanation: string;
      real_world_analogy: string;
      step_by_step: string[];
    }>("/agents/learn", { method: "POST", body: JSON.stringify(body) }, token),
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
  crashRecoveryLogs: (token: string) =>
    requestJson<{ crashes: Array<{ timestamp: string; path: string; error: string }> }>(
      "/self-healing/crashes",
      { method: "GET" },
      token
    ),
};
