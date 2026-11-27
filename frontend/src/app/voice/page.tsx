"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Activity, Mic, MicOff, RefreshCw, Shield, Volume2, Wifi, WifiOff, Wrench } from "lucide-react";
import { BrandLoader } from "@/components/BrandLoader";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import {
  AudioDiagnosticsResponse,
  MicRecoverResponse,
  MicTestResponse,
  VoiceStatusResponse,
  ecosystemApi,
} from "@/lib/api";

const SUPPORTED_LANGUAGES = [
  "Hindi", "English", "Hinglish", "Bengali", "Tamil", "Telugu", "Gujarati",
  "Marathi", "Punjabi", "Kannada", "Malayalam", "Urdu", "Assamese", "Odia",
];

const VOICE_PERSONALITIES = [
  { id: "aanya-warm", label: "Aanya — Warm Companion (en-IN / hi-IN)" },
  { id: "kavya-executive", label: "Kavya — Crisp Executive (en-IN)" },
  { id: "meera-mentor", label: "Meera — Calm Study Mentor (hi-IN)" },
  { id: "riya-hinglish", label: "Riya — Expressive Hinglish" },
];

const DEVICE_TYPE_BADGES: Record<string, string> = {
  usb: "bg-sky-500/20 text-sky-400 border border-sky-500/30",
  bluetooth: "bg-violet-500/20 text-violet-400 border border-violet-500/30",
  integrated: "bg-slate-500/20 text-slate-300 border border-slate-500/30",
  virtual: "bg-amber-500/20 text-amber-400 border border-amber-500/30",
  unknown: "bg-gray-500/20 text-gray-400 border border-gray-500/30",
};

function classifyBrowserDeviceType(label: string): string {
  const lower = label.toLowerCase();
  if (/stereo mix|voicemeeter|virtual|vb-audio|loopback|mapper/.test(lower)) return "virtual";
  if (/usb|yeti|shure|fifine|hyperx|rode|webcam/.test(lower)) return "usb";
  if (/bluetooth|hands-free|airpods|buds|headset|wireless/.test(lower)) return "bluetooth";
  if (/array|realtek|intel|built-in|internal|digital mic|integrated/.test(lower)) return "integrated";
  return "unknown";
}

function MicStatusBadge({ connected, deviceName }: { connected: boolean; deviceName?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
        connected
          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
          : "bg-red-500/20 text-red-400 border border-red-500/30"
      }`}
    >
      {connected ? "🟢" : "🔴"} {connected ? `MIC: CONNECTED${deviceName ? ` • ${deviceName}` : ""}` : "MIC: NOT FOUND"}
    </span>
  );
}

function VoiceWorkspaceContent({
  token,
  setStatusNote,
}: {
  token: string;
  setStatusNote: (note: string) => void;
}) {
  const [transcript, setTranscript] = useState("Hey Nova bhai aaj ka plan batao");
  const [personality, setPersonality] = useState("aanya-warm");
  const [listenMode, setListenMode] = useState<"always" | "ptt" | "wake">("always");
  const [noiseSuppression, setNoiseSuppression] = useState(true);
  const [muted, setMuted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resultSummary, setResultSummary] = useState(
    "Live Companion Mode active — auto-detects 14 Indian languages + Hinglish, retains language memory, and supports barge-in interruption."
  );

  const [diagData, setDiagData] = useState<AudioDiagnosticsResponse | null>(null);
  const [testResult, setTestResult] = useState<MicTestResponse | null>(null);
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatusResponse | null>(null);
  const [recoverResult, setRecoverResult] = useState<MicRecoverResponse | null>(null);
  const [selectedDeviceIdx, setSelectedDeviceIdx] = useState<number>(0);
  const [diagBusy, setDiagBusy] = useState(false);
  const [troubleshootOpen, setTroubleshootOpen] = useState(false);
  const [setupDone, setSetupDone] = useState(true);

  useEffect(() => {
    try {
      setSetupDone(Boolean(window.sessionStorage.getItem("mic_setup_done")));
    } catch {
      setSetupDone(true);
    }
  }, []);

  const probeBrowserFallbackDevices = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.enumerateDevices) {
      return;
    }
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const mics = devices.filter((d) => d.kind === "audioinput");
      if (mics.length > 0) {
        const mapped = mics.map((m, idx) => ({
          index: idx,
          name: m.label || `Browser Audio Input #${idx + 1}`,
          display_name: m.label || `Browser Audio Input #${idx + 1}`,
          device_type: classifyBrowserDeviceType(m.label || ""),
          default_samplerate: 48000,
          driver_status: "Available (Browser Web Audio)",
          is_default: idx === 0,
        }));
        setDiagData({
          mic_available: true,
          mic_status: "CONNECTED",
          input_devices: mapped,
          output_devices: [],
          best_device: mapped[0],
          active_device: mapped[0],
          health_status: "healthy",
          issues_detected: [],
          repair_guidance: [
            "Browser audio endpoints enumerated cleanly. Connect JWT for full Windows WASAPI/MME PortAudio diagnostics.",
          ],
        });
      }
    } catch {
      /* ignore browser enumeration restrictions */
    }
  }, []);

  const loadDevices = useCallback(async () => {
    setDiagBusy(true);
    try {
      if (!token) {
        await probeBrowserFallbackDevices();
        return;
      }
      const [data, vs] = await Promise.all([
        ecosystemApi.voiceDiagnosticsDevices(token),
        ecosystemApi.voiceStatus(token),
      ]);
      setDiagData(data);
      const chosen = data.active_device ?? data.best_device;
      if (chosen) setSelectedDeviceIdx(chosen.index);
      setVoiceStatus(vs);
      setMuted(Boolean(vs.muted));
    } catch {
      await probeBrowserFallbackDevices();
    } finally {
      setDiagBusy(false);
    }
  }, [token, probeBrowserFallbackDevices]);

  useEffect(() => {
    void loadDevices();
  }, [loadDevices]);

  const runDiag = async () => {
    await loadDevices();
    setStatusNote("Microphone devices refreshed.");
  };

  const runTest = async () => {
    setDiagBusy(true);
    try {
      if (token) {
        const r = await ecosystemApi.voiceTestMic(token, { device_index: selectedDeviceIdx });
        setTestResult(r);
        setStatusNote(`Mic test: ${r.signal_quality.toUpperCase()} | Volume=${r.volume_percent ?? 0}%`);
      } else if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        try {
          const ctx = new AudioContext();
          const src = ctx.createMediaStreamSource(stream);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 512;
          src.connect(analyser);
          const buf = new Float32Array(analyser.fftSize);
          await new Promise((r) => setTimeout(r, 200));
          analyser.getFloatTimeDomainData(buf);
          let sum = 0;
          for (let i = 0; i < buf.length; i += 1) sum += buf[i] * buf[i];
          const rms = Math.sqrt(sum / buf.length);
          const pct = rms > 1e-6 ? Math.max(8, Math.min(100, Math.round(rms * 400))) : 0;
          setTestResult({
            rms_level: Number(rms.toFixed(5)),
            volume_percent: pct,
            signal_quality: rms > 0.001 ? "ok" : "quiet_ready",
            device_opened: true,
            mic_available: true,
            best_device: diagData?.best_device ?? null,
            issues: [],
            guidance: ["Web Audio microphone test passed."],
          });
          await ctx.close();
        } finally {
          stream.getTracks().forEach((t) => t.stop());
        }
      } else {
        setTestResult({
          rms_level: 0.0,
          volume_percent: 0,
          signal_quality: "unavailable",
          mic_available: false,
          best_device: null,
          issues: ["Connect JWT backend or grant browser microphone permission to run hardware capture."],
          guidance: ["Click Connect JWT to test Windows WASAPI microphones."],
        });
      }
    } catch (err) {
      setStatusNote(`Mic test note: ${err instanceof Error ? err.message : "Permission required"}`);
    } finally {
      setDiagBusy(false);
    }
  };

  const changeMic = async () => {
    if (!token) {
      setStatusNote(`Selected input device #${selectedDeviceIdx} for browser session.`);
      return;
    }
    setDiagBusy(true);
    try {
      const updated = await ecosystemApi.voiceChangeMic(token, selectedDeviceIdx);
      setDiagData(updated);
      setStatusNote(`Active microphone switched to ${updated.active_device_name}.`);
      const vs = await ecosystemApi.voiceStatus(token);
      setVoiceStatus(vs);
    } finally {
      setDiagBusy(false);
    }
  };

  const recoverMic = async () => {
    setDiagBusy(true);
    try {
      if (!token) {
        await probeBrowserFallbackDevices();
        setRecoverResult({
          status: diagData?.mic_available ? "recovered" : "no_devices",
          device: diagData?.best_device ?? null,
          steps_attempted: ["Rescanned browser audio devices."],
        });
        return;
      }
      const r = await ecosystemApi.voiceRecoverMic(token);
      setRecoverResult(r);
      setStatusNote(`Recovery: ${r.mic_status ?? r.status}`);
      await loadDevices();
    } finally {
      setDiagBusy(false);
    }
  };

  const toggleMute = async () => {
    const nextMuted = !muted;
    setMuted(nextMuted);
    if (token) {
      const vs = await ecosystemApi.voiceMute(token, nextMuted);
      setVoiceStatus(vs);
    }
  };

  const activeDevice = diagData?.active_device ?? diagData?.best_device ?? null;
  const micConnected = Boolean(diagData?.mic_available ?? voiceStatus?.mic_connected ?? false);
  const devName = activeDevice?.display_name ?? activeDevice?.name ?? voiceStatus?.current_device_name ?? "";
  const devType = activeDevice?.device_type ?? voiceStatus?.current_device_type ?? "unknown";
  const sampleRate = activeDevice?.default_samplerate ?? voiceStatus?.sample_rate ?? null;
  const driverStatus = activeDevice?.driver_status ?? voiceStatus?.driver_status ?? (micConnected ? "Available" : "Pending Check");
  const volPercent = testResult?.volume_percent ?? voiceStatus?.voice_activity_percent ?? 0;

  return (
    <div className="space-y-5">
      {/* ── First Launch Setup Wizard Card ── */}
      {!setupDone && (
        <GlassCard>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <Mic className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
              <div>
                <p className="text-sm font-bold text-amber-400">
                  First-Launch Microphone Setup Wizard
                </p>
                <p className="text-xs text-adaptive-muted">
                  1. Verify Windows &amp; browser microphone permissions &bull; 2. Auto-test your best mic &bull; 3. Confirm readiness.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void runTest()}
                className="min-h-[36px] rounded-lg bg-aspirant-gradient px-3 py-1 text-xs font-semibold text-white"
              >
                Auto-Test Mic
              </button>
              <button
                type="button"
                onClick={() => {
                  try {
                    window.sessionStorage.setItem("mic_setup_done", "1");
                  } catch {
                    /* ignore */
                  }
                  setSetupDone(true);
                }}
                className="surface-card min-h-[36px] rounded-lg px-3 py-1 text-xs font-semibold hover:border-sky-500"
              >
                Complete Setup
              </button>
            </div>
          </div>
        </GlassCard>
      )}

      {/* ── Live Voice Companion Controls ── */}
      <GlassCard>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Mic className="h-6 w-6 text-sky-500 dark:text-sky-400" />
            <div>
              <h2 className="text-lg font-bold">Live AI Companion &amp; Multilingual Voice Studio</h2>
              <p className="text-xs text-adaptive-muted">
                Streaming recognition &bull; 14 Languages + Hinglish &bull; Personalities &bull; Barge-In Interruption
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <MicStatusBadge connected={micConnected} deviceName={devName} />
            <label htmlFor="listen-mode-select" className="sr-only">Voice Activation Mode</label>
            <select
              id="listen-mode-select"
              value={listenMode}
              onChange={(e) => setListenMode(e.target.value as "always" | "ptt" | "wake")}
              className="select-surface min-h-[36px] rounded-xl px-3 py-1.5 text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              <option value="always">Continuous Listening Mode</option>
              <option value="wake">Wake Word (&ldquo;Hey Nova / Aspirant&rdquo;)</option>
              <option value="ptt">Push-to-Talk Mode</option>
            </select>
            <label htmlFor="voice-personality-select" className="sr-only">Voice Personality</label>
            <select
              id="voice-personality-select"
              value={personality}
              onChange={(e) => setPersonality(e.target.value)}
              className="select-surface min-h-[36px] rounded-xl px-3 py-1.5 text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              {VOICE_PERSONALITIES.map((v) => (
                <option key={v.id} value={v.id}>{v.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <label htmlFor="voice-transcript" className="sr-only">Voice Transcript</label>
          <input
            id="voice-transcript"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            className="input-surface flex-1 rounded-xl px-3 py-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          />
          <button
            type="button"
            onClick={() => void toggleMute()}
            className="surface-card inline-flex min-h-[40px] items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold hover:border-amber-500"
          >
            {muted ? <MicOff className="h-3.5 w-3.5 text-amber-400" /> : <Mic className="h-3.5 w-3.5 text-emerald-400" />}
            <span>{muted ? "Unmute" : "Mute Mic"}</span>
          </button>
          <button
            type="button"
            onClick={async () => {
              setBusy(true);
              try {
                if (token) {
                  const res = await ecosystemApi.voiceProcess(token, {
                    transcript,
                    always_listening: listenMode === "always",
                    noise_db: noiseSuppression ? -42 : -22,
                  });
                  setResultSummary(
                    `Lang=${res.language_name} | Intent=${res.detected_intent} | Confidence=${res.confidence} | Access=${res.access_level} | Reply: ${res.reply_text}`
                  );
                  setStatusNote(`Processed live utterance in ${res.language_name}.`);
                } else {
                  setResultSummary(
                    `Preview (${personality}, mode=${listenMode}): detected Hindi/Hinglish code-switching & queued interruptible reply.`
                  );
                }
              } finally {
                setBusy(false);
              }
            }}
            className="inline-flex min-h-[40px] items-center justify-center gap-1.5 rounded-xl bg-aspirant-gradient px-4 py-2 text-xs font-semibold text-white"
          >
            <Volume2 className="h-3.5 w-3.5" /> Speak &amp; Preview
          </button>
        </div>

        {busy && (
          <div className="mt-3">
            <BrandLoader label="Streaming multilingual neural response..." size={32} />
          </div>
        )}

        <p className="surface-card mt-3 rounded-xl p-3 text-xs text-sky-700 dark:text-sky-300">
          {resultSummary}
        </p>
      </GlassCard>

      {/* ── Voice Control Dashboard (Always Visible) ── */}
      <GlassCard>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-violet-400" />
            <h3 className="text-sm font-bold">Voice Control Dashboard</h3>
          </div>
          <span className="text-xs font-semibold">
            {muted ? "🔇 Muted" : micConnected ? "🎤 Listening Ready" : "🔴 Disconnected"}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-3">
          <div>
            <span className="text-adaptive-muted">Listening Status</span>
            <p className="font-semibold">
              {muted ? "🔇 Muted" : listenMode === "always" ? "🎤 Listening (Continuous)" : listenMode === "wake" ? "🎤 Armed (Wake Word)" : "🎤 Push-to-Talk"}
            </p>
          </div>
          <div>
            <span className="text-adaptive-muted">Wake Word Status</span>
            <p className="font-semibold">
              {listenMode === "wake" || voiceStatus?.wake_word_armed ? "🟢 Connected (Armed)" : "🔴 Disconnected"}
            </p>
          </div>
          <div>
            <span className="text-adaptive-muted">Speech Recognition Status</span>
            <p className="font-semibold">
              {muted ? "🔇 Muted" : micConnected ? "🟢 Connected (Ready)" : "🔴 Disconnected"}
            </p>
          </div>
          <div>
            <span className="text-adaptive-muted">Noise Suppression Status</span>
            <p className="font-semibold">
              <button
                type="button"
                onClick={() => setNoiseSuppression((prev) => !prev)}
                className="underline decoration-dotted underline-offset-2"
              >
                {noiseSuppression ? "🟢 Connected (WebRTC VAD ON)" : "🔇 Muted (OFF)"}
              </button>
            </p>
          </div>
          <div>
            <span className="text-adaptive-muted">Connection State</span>
            <p className="font-semibold">{micConnected ? "🟢 Connected" : "🔴 Disconnected"}</p>
          </div>
          <div>
            <span className="text-adaptive-muted">Voice Activity Meter</span>
            <div className="mt-1 flex items-center gap-2">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-700/40 dark:bg-slate-800">
                <div
                  className="h-full rounded-full bg-sky-400 transition-all duration-300"
                  style={{ width: `${muted ? 0 : volPercent}%` }}
                />
              </div>
              <span className="font-semibold">{muted ? "0%" : `${volPercent}%`}</span>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* ── Microphone Diagnostic Center (Always Visible) ── */}
      <GlassCard>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-violet-600 dark:text-violet-400">
            <Wrench className="h-4 w-4" />
            <h3 className="text-sm font-bold">Microphone Diagnostic Center</h3>
          </div>
          <MicStatusBadge connected={micConnected} deviceName={devName} />
        </div>

        <div className="mb-4 grid grid-cols-2 gap-x-6 gap-y-3 text-xs sm:grid-cols-3">
          <div>
            <span className="text-adaptive-muted">Connected Microphone Name</span>
            <p className="font-semibold">{devName || "Awaiting Device Scan"}</p>
          </div>
          <div>
            <span className="text-adaptive-muted">Device Status</span>
            <p className="font-semibold">
              {micConnected ? "🟢 MIC: CONNECTED" : "🔴 MIC: NOT FOUND"}
              <span className={`ml-2 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${DEVICE_TYPE_BADGES[devType] ?? DEVICE_TYPE_BADGES.unknown}`}>
                {devType.toUpperCase()}
              </span>
            </p>
          </div>
          <div>
            <span className="text-adaptive-muted">Driver Status</span>
            <p className="font-semibold">{driverStatus}</p>
          </div>
          <div>
            <span className="text-adaptive-muted">Sample Rate</span>
            <p className="font-semibold">{sampleRate ? `${sampleRate} Hz` : "—"}</p>
          </div>
          <div>
            <span className="text-adaptive-muted">Input Volume Level</span>
            <p className="font-semibold">{volPercent}% {testResult?.db_level != null ? `(${testResult.db_level} dBFS)` : ""}</p>
          </div>
          <div>
            <span className="text-adaptive-muted">Test Result</span>
            <p className="font-semibold">
              {testResult
                ? `${testResult.signal_quality === "ok" || testResult.signal_quality === "quiet_ready" ? "🟢" : testResult.signal_quality === "muted" ? "🔇" : "🔴"} ${testResult.signal_quality.toUpperCase()} (RMS=${testResult.rms_level.toFixed(4)})`
                : "Ready to test"}
            </p>
          </div>
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <label htmlFor="device-selector" className="text-xs text-adaptive-muted">Select Microphone:</label>
          <select
            id="device-selector"
            value={selectedDeviceIdx}
            onChange={(e) => setSelectedDeviceIdx(Number(e.target.value))}
            className="select-surface min-h-[36px] min-w-[220px] flex-1 rounded-xl px-3 py-1.5 text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            {diagData && diagData.input_devices.length > 0 ? (
              diagData.input_devices.map((d) => (
                <option key={d.index} value={d.index}>
                  {d.display_name || d.name} [{d.device_type.toUpperCase()}]
                </option>
              ))
            ) : (
              <option value={0}>Default System Microphone (Scan pending)</option>
            )}
          </select>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void runDiag()}
            disabled={diagBusy}
            className="surface-card inline-flex min-h-[36px] items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold hover:border-sky-500 disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh Devices
          </button>
          <button
            type="button"
            onClick={() => void runTest()}
            disabled={diagBusy}
            className="inline-flex min-h-[36px] items-center gap-1.5 rounded-lg bg-aspirant-gradient px-3 py-1 text-xs font-semibold text-white disabled:opacity-50"
          >
            <Mic className="h-3.5 w-3.5" /> Test Microphone
          </button>
          <button
            type="button"
            onClick={() => void changeMic()}
            disabled={diagBusy}
            className="surface-card inline-flex min-h-[36px] items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold hover:border-sky-500 disabled:opacity-50"
          >
            Change Microphone
          </button>
          <button
            type="button"
            onClick={() => void recoverMic()}
            disabled={diagBusy}
            className="surface-card inline-flex min-h-[36px] items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold hover:border-emerald-500 disabled:opacity-50"
          >
            {micConnected ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />} Reconnect Microphone
          </button>
          <button
            type="button"
            onClick={() => setTroubleshootOpen((v) => !v)}
            className="surface-card inline-flex min-h-[36px] items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold hover:border-amber-500"
          >
            <Wrench className="h-3.5 w-3.5" /> Troubleshoot Audio
          </button>
        </div>

        {diagBusy && (
          <div className="mt-3">
            <BrandLoader label="Scanning audio devices..." size={28} />
          </div>
        )}

        {troubleshootOpen && (
          <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs">
            <p className="font-bold text-amber-400">Audio Troubleshooting Checklist</p>
            <ul className="mt-1 list-inside list-disc space-y-1 text-adaptive-body">
              <li>Windows Settings &rarr; Privacy &amp; security &rarr; Microphone &rarr; Allow desktop apps to access your microphone.</li>
              <li>Select a Windows WASAPI microphone in &ldquo;Select Microphone&rdquo; and click &ldquo;Change Microphone&rdquo;.</li>
              <li>Check USB/Bluetooth power &amp; click &ldquo;Reconnect Microphone&rdquo; to rescan audio subsystem without restart.</li>
            </ul>
          </div>
        )}

        {diagData && diagData.issues_detected.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3">
            <p className="mb-1 text-xs font-bold text-amber-400">Diagnostics Notes</p>
            <ul className="list-inside list-disc space-y-1">
              {diagData.issues_detected.map((issue, i) => (
                <li key={i} className="text-xs text-amber-300">{issue}</li>
              ))}
            </ul>
          </div>
        )}

        {recoverResult && (
          <p className={`mt-2 text-xs font-semibold ${recoverResult.status === "recovered" ? "text-emerald-400" : "text-amber-400"}`}>
            {recoverResult.status === "recovered"
              ? `🟢 ${recoverResult.mic_status ?? "MIC: CONNECTED"} — ${recoverResult.device?.display_name ?? recoverResult.device?.name}`
              : `🔴 MIC: NOT FOUND — ${recoverResult.error ?? "Check microphone connection."}`}
          </p>
        )}

        <p className="mt-3 flex items-center gap-1.5 text-[11px] text-adaptive-muted">
          <Shield className="h-3.5 w-3.5 text-emerald-500" />
          Voice cloning hooks &amp; speaker verification require password fallback for changes.
        </p>
      </GlassCard>

      {/* ── Bottom Row: Languages + Detected Devices ── */}
      <div className="grid gap-4 md:grid-cols-2">
        <GlassCard>
          <h3 className="text-sm font-bold text-sky-600 dark:text-sky-400">
            14 Supported Languages + Code-Switching
          </h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {SUPPORTED_LANGUAGES.map((lang) => (
              <span key={lang} className="surface-card rounded-lg px-2.5 py-1 text-xs font-medium">
                {lang}
              </span>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <h3 className="mb-3 text-sm font-bold text-violet-600 dark:text-violet-400">
            Detected Audio Input Devices ({diagData?.input_devices.length ?? 0})
          </h3>
          {diagData && diagData.input_devices.length > 0 ? (
            <div className="space-y-2">
              {diagData.input_devices.slice(0, 8).map((d) => (
                <div key={d.index} className="flex items-center justify-between gap-2 text-xs">
                  <span className="truncate font-medium">{d.display_name || d.name}</span>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${DEVICE_TYPE_BADGES[d.device_type] ?? DEVICE_TYPE_BADGES.unknown}`}>
                      {d.device_type.toUpperCase()}
                    </span>
                    <span className="text-adaptive-muted">{d.default_samplerate} Hz</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-adaptive-muted">
              Click Refresh Devices or Connect JWT to inspect all USB, Bluetooth, integrated, and virtual microphones.
            </p>
          )}
        </GlassCard>
      </div>
    </div>
  );
}

export default function VoicePage() {
  return (
    <WorkspaceShell routeId="voice">
      {({ token, setStatusNote }) => (
        <VoiceWorkspaceContent token={token} setStatusNote={setStatusNote} />
      )}
    </WorkspaceShell>
  );
}
