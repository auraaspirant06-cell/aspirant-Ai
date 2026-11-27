"use client";

import React, { useState } from "react";
import { Share2 } from "lucide-react";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

const PLATFORMS = [
  { platform: "telegram", name: "Telegram Bot API", scope: "Official Bot Token • webhooks & replies" },
  { platform: "youtube", name: "YouTube Data API v3", scope: "OAuth2 • analytics & channel metadata" },
  { platform: "instagram", name: "Instagram Business Graph", scope: "Meta Graph v21 • media & insights" },
  { platform: "discord", name: "Discord REST v10", scope: "Official Bot • slash commands & channels" },
  { platform: "x", name: "X Platform API v2", scope: "OAuth2 PKCE • rate-limited compliant access" },
];

export default function IntegrationsPage() {
  const [syncText, setSyncText] = useState("All connectors operate strictly via official REST APIs with encrypted tokens and rate limits.");

  return (
    <WorkspaceShell routeId="integrations">
      {({ token, setStatusNote }) => (
        <GlassCard>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Share2 className="h-5 w-5 text-violet-400" />
              <h2 className="text-lg font-bold">Modular Social Platform Connectors</h2>
            </div>
            <button
              type="button"
              onClick={async () => {
                if (token) {
                  const res = await ecosystemApi.integrationsCatalog(token);
                  setSyncText(`Loaded ${res.connectors.length} official API connectors from backend.`);
                  setStatusNote("Refreshed integration connector catalog.");
                }
              }}
              className="rounded-xl border border-white/10 px-3 py-1.5 text-xs font-semibold hover:border-sky-500"
            >
              Refresh Connector Status
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-400">{syncText}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-xs">
            {PLATFORMS.map((p) => (
              <div key={p.platform} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                <p className="font-bold text-sky-400">{p.name}</p>
                <p className="mt-1 text-slate-400">{p.scope}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </WorkspaceShell>
  );
}
