"use client";

import React, { useState } from "react";
import Link from "next/link";
import { BrandMark } from "@/components/BrandMark";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

export default function NovaPage() {
  const [clipboardSample, setClipboardSample] = useState(
    "def analyze_pipeline():\n    return True"
  );
  const [clipboardKind, setClipboardKind] = useState("code");

  return (
    <WorkspaceShell routeId="nova">
      {({ token, setStatusNote }) => (
        <GlassCard>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <BrandMark product="nova" size={44} />
              <div>
                <h2 className="text-lg font-bold">NOVA Desktop Control & Automation</h2>
                <p className="text-xs text-slate-400">
                  Wake word &ldquo;Hey Nova&rdquo; • Clipboard Intelligence • WinRT OCR • Safe Terminal Guard
                </p>
              </div>
            </div>
            <Link
              href="/voice"
              className="rounded-xl border border-sky-500/40 px-3 py-1.5 text-xs font-semibold text-sky-300 hover:bg-sky-500/10"
            >
              Configure Voice & Speaker Unlock
            </Link>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="space-y-2 rounded-xl border border-white/10 p-4">
              <label htmlFor="clipboard-box" className="text-xs font-semibold text-sky-400">
                Clipboard Intelligence Inspector ({clipboardKind})
              </label>
              <textarea
                id="clipboard-box"
                rows={4}
                value={clipboardSample}
                onChange={(e) => setClipboardSample(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-black/25 p-3 font-mono text-xs outline-none focus:border-sky-500"
              />
              <button
                type="button"
                onClick={async () => {
                  if (token) {
                    const res = await ecosystemApi.novaClipboard(token, clipboardSample);
                    setClipboardKind(res.kind);
                    setStatusNote(`NOVA classified clipboard as '${res.kind}'.`);
                    return;
                  }
                  setClipboardKind(clipboardSample.includes("def ") ? "code" : "plain_text");
                  setStatusNote("Analyzed clipboard sample locally.");
                }}
                className="rounded-xl bg-sky-500/20 px-3 py-1.5 text-xs font-semibold text-sky-300 hover:bg-sky-500/30"
              >
                Classify & Suggest NOVA Actions
              </button>
            </div>
            <div className="space-y-2 rounded-xl border border-white/10 p-4 text-xs text-slate-300">
              <p className="font-semibold text-violet-400">Desktop Capabilities Active</p>
              <p>• Global Hotkey Bridge: Ctrl+Shift+N &amp; Tray Quick Menu</p>
              <p>• Isolated Edge Playwright Automation + Policy Approval Queue</p>
              <p>• Gemini 3.8 Live Female Natural Voice + 13 Indic Languages</p>
              <p>• Explicit Authorization Gate for Sensitive OS/File Commands</p>
            </div>
          </div>
        </GlassCard>
      )}
    </WorkspaceShell>
  );
}
