"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, KeyRound, Settings } from "lucide-react";
import { ecosystemApi } from "@/lib/api";
import { getRouteById, type RouteId } from "@/lib/routes";
import { Sidebar } from "./Sidebar";

interface WorkspaceShellProps {
  routeId: RouteId;
  children: (ctx: {
    token: string;
    setStatusNote: (note: string) => void;
  }) => React.ReactNode;
}

export function WorkspaceShell({ routeId, children }: WorkspaceShellProps) {
  const route = getRouteById(routeId);
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("founder@aspirant.ai");
  const [password, setPassword] = useState("StrongPassword!2026");
  const [statusNote, setStatusNote] = useState(
    "Ready — connect to FastAPI backend or inspect offline console."
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const saved = window.sessionStorage.getItem("aspirant_jwt") || "";
    if (saved) setToken(saved);
  }, []);

  const handleAuthenticate = async () => {
    setBusy(true);
    try {
      let auth;
      try {
        auth = await ecosystemApi.login({ email, password });
      } catch {
        auth = await ecosystemApi.register({ email, password, full_name: "Aspirant Owner" });
      }
      setToken(auth.access_token);
      window.sessionStorage.setItem("aspirant_jwt", auth.access_token);
      setStatusNote(`Authenticated as ${auth.user.email} (JWT session active).`);
    } catch (err) {
      setStatusNote(
        `Offline UI preview mode (${err instanceof Error ? err.message : "backend unreachable"}).`
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-screen-id={route.id}
      data-component-name={route.componentName}
      className="mx-auto flex min-h-screen max-w-7xl flex-col gap-5 p-4 md:p-6 lg:flex-row"
    >
      <Sidebar activeTab={route.id} />

      <main className="flex-1 space-y-5">
        <header className="glass-panel flex flex-col justify-between gap-4 rounded-2xl p-5 sm:flex-row sm:items-center">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-sky-400">
              <Activity className="h-3.5 w-3.5" />
              <span>Unified Personal AI Operating System • {route.href}</span>
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight">
              <span className="gradient-text">{route.screenTitle}</span>
            </h1>
            <p className="mt-1 text-xs text-slate-400">{statusNote}</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="auth-email" className="sr-only">
              Email
            </label>
            <input
              id="auth-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-1.5 text-xs outline-none focus:border-sky-500"
            />
            <label htmlFor="auth-pass" className="sr-only">
              Password
            </label>
            <input
              id="auth-pass"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-32 rounded-xl border border-white/10 bg-black/20 px-3 py-1.5 text-xs outline-none focus:border-sky-500"
            />
            <button
              type="button"
              onClick={handleAuthenticate}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-xl bg-aspirant-gradient px-3.5 py-1.5 text-xs font-semibold text-white"
            >
              <KeyRound className="h-3.5 w-3.5" />
              <span>{token ? "Connected" : "Connect JWT"}</span>
            </button>
            <Link
              href="/settings"
              aria-label="Open System Settings"
              className="rounded-xl border border-white/10 p-1.5 text-slate-300 hover:border-sky-500 hover:text-sky-400"
            >
              <Settings className="h-4 w-4" />
            </Link>
          </div>
        </header>

        {children({ token, setStatusNote })}
      </main>
    </div>
  );
}
