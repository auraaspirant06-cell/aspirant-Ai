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
  const [windowsSummary, setWindowsSummary] = useState(
    "Window manager, app launcher, file organizer, notifications & WinRT OCR standing by."
  );

  return (
    <WorkspaceShell routeId="nova">
      {({ token, setStatusNote }) => (
        <GlassCard>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <BrandMark product="nova" size={44} />
              <div>
                <h2 className="text-lg font-bold">NOVA Windows Integration &amp; Automation</h2>
                <p className="text-xs text-adaptive-muted">
                  Window Management &bull; App Launching &bull; File Search &amp; Org &bull; Clipboard &bull; OCR
                </p>
              </div>
            </div>
            <Link
              href="/voice"
              className="surface-card inline-flex min-h-[40px] items-center rounded-xl px-3 py-1.5 text-xs font-semibold text-sky-600 hover:border-sky-500 dark:text-sky-400"
            >
              Configure Voice &amp; Mic Diagnostics
            </Link>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="surface-card space-y-2 rounded-xl p-4">
              <label
                htmlFor="clipboard-box"
                className="text-xs font-semibold text-sky-600 dark:text-sky-400"
              >
                Clipboard Intelligence Inspector ({clipboardKind})
              </label>
              <textarea
                id="clipboard-box"
                rows={4}
                value={clipboardSample}
                onChange={(e) => setClipboardSample(e.target.value)}
                className="input-surface w-full rounded-xl p-3 font-mono text-xs outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
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
                className="min-h-[40px] rounded-xl bg-aspirant-gradient px-3.5 py-2 text-xs font-semibold text-white"
              >
                Classify &amp; Suggest NOVA Actions
              </button>
            </div>
            <div className="surface-card space-y-3 rounded-xl p-4 text-xs">
              <p className="font-semibold text-violet-600 dark:text-violet-400">
                Windows 11 Operating Layer
              </p>
              <p className="text-adaptive-body">{windowsSummary}</p>
              <ul className="space-y-1 text-adaptive-muted">
                <li>&bull; Enumerate, focus, minimize, or close desktop windows (gated)</li>
                <li>&bull; Search files, organize folders with dry-run preview &amp; WinRT toasts</li>
                <li>&bull; Screen understanding + explicit approval on destructive OS actions</li>
              </ul>
              <button
                type="button"
                onClick={async () => {
                  if (token) {
                    const res = await ecosystemApi.novaWindowsList(token);
                    setWindowsSummary(
                      `Platform=${res.platform}: detected ${res.windows.length} visible window(s).`
                    );
                    setStatusNote("Queried active desktop windows via NOVA.");
                  } else {
                    setWindowsSummary("Preview: Windows EnumWindows + Search + File Organizer ready (connect JWT for live probe).");
                  }
                }}
                className="surface-card min-h-[40px] rounded-xl px-3.5 py-2 font-semibold hover:border-sky-500"
              >
                Probe Active Windows
              </button>
            </div>
          </div>
        </GlassCard>
      )}
    </WorkspaceShell>
  );
}
