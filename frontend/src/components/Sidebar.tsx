"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Brain,
  Cpu,
  LayoutDashboard,
  Mic,
  Moon,
  Settings,
  Share2,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Sun,
  Terminal,
} from "lucide-react";
import { APP_ROUTES, normalizePathname, type RouteId } from "@/lib/routes";
import { BrandMark } from "./BrandMark";
import { useTheme } from "./ThemeProvider";

export type WorkspaceTab = RouteId;

const ICON_MAP: Record<RouteId, React.ComponentType<{ className?: string }>> = {
  overview: LayoutDashboard,
  nova: Terminal,
  mj: Brain,
  max: Smartphone,
  voice: Mic,
  agents: Cpu,
  memory: Sparkles,
  integrations: Share2,
  security: ShieldCheck,
  settings: Settings,
};

interface SidebarProps {
  activeTab?: RouteId;
}

export function Sidebar({ activeTab }: SidebarProps) {
  const pathname = normalizePathname(usePathname() || "/");
  const { theme, toggleTheme } = useTheme();

  return (
    <aside
      aria-label="Primary Ecosystem Navigation"
      className="glass-panel flex flex-col justify-between rounded-2xl p-4 lg:w-64 lg:shrink-0"
    >
      <div>
        <Link href="/" className="flex items-center gap-3 px-2 pb-5 pt-1 focus:outline-none">
          <BrandMark product="aspirant" size={40} />
          <div>
            <p className="text-sm font-bold tracking-widest gradient-text">ASPIRANT AI</p>
            <p className="text-[11px] text-slate-400">Intelligence Beyond Assistance</p>
          </div>
        </Link>

        <nav className="grid grid-cols-2 gap-1.5 sm:grid-cols-4 lg:grid-cols-1">
          {APP_ROUTES.map((item) => {
            const Icon = ICON_MAP[item.id];
            const active = activeTab ? activeTab === item.id : pathname === item.href;
            return (
              <Link
                key={item.id}
                href={item.href}
                data-route-id={item.id}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-xl px-3 py-2 text-left transition-all focus:outline-none focus:ring-2 focus:ring-sky-500 ${
                  active
                    ? "bg-aspirant-gradient text-white shadow-glow"
                    : "text-slate-600 hover:bg-slate-200/60 dark:text-slate-300 dark:hover:bg-white/5"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold">{item.label}</div>
                  <div
                    className={`truncate text-[11px] ${
                      active ? "text-white/80" : "text-slate-400"
                    }`}
                  >
                    {item.sublabel}
                  </div>
                </div>
              </Link>
            );
          })}
        </nav>
      </div>

      <button
        type="button"
        onClick={toggleTheme}
        aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        className="mt-4 flex items-center justify-between rounded-xl border border-slate-300/60 px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-sky-500 dark:border-white/10 dark:text-slate-200"
      >
        <span>{theme === "dark" ? "Deep Space Dark" : "Clean Daylight"}</span>
        {theme === "dark" ? (
          <Sun className="h-4 w-4 text-sky-400" />
        ) : (
          <Moon className="h-4 w-4 text-violet-500" />
        )}
      </button>
    </aside>
  );
}
