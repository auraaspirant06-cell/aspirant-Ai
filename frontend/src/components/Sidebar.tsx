"use client";

import React from "react";
import {
  Brain,
  Cpu,
  LayoutDashboard,
  Moon,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Sun,
  Terminal,
} from "lucide-react";
import { BrandMark } from "./BrandMark";
import { useTheme } from "./ThemeProvider";

export type WorkspaceTab =
  | "overview"
  | "nova"
  | "mj"
  | "max"
  | "agents"
  | "memory"
  | "security";

interface SidebarProps {
  activeTab: WorkspaceTab;
  onSelect: (tab: WorkspaceTab) => void;
}

const NAV_ITEMS: Array<{
  id: WorkspaceTab;
  label: string;
  sublabel: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  { id: "overview", label: "Ecosystem", sublabel: "Command Center", icon: LayoutDashboard },
  { id: "nova", label: "NOVA", sublabel: "Windows Desktop", icon: Terminal },
  { id: "mj", label: "MJ", sublabel: "Human Intelligence", icon: Brain },
  { id: "max", label: "MAX", sublabel: "Mobile Companion", icon: Smartphone },
  { id: "agents", label: "7 Agents", sublabel: "Orchestrator", icon: Cpu },
  { id: "memory", label: "Memory & RAG", sublabel: "Qdrant + Chroma", icon: Sparkles },
  { id: "security", label: "Security", sublabel: "JWT & Audit", icon: ShieldCheck },
];

export function Sidebar({ activeTab, onSelect }: SidebarProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <aside
      aria-label="Primary Ecosystem Navigation"
      className="glass-panel flex flex-col justify-between rounded-2xl p-4 lg:w-64 lg:shrink-0"
    >
      <div>
        <div className="flex items-center gap-3 px-2 pb-5 pt-1">
          <BrandMark product="aspirant" size={40} />
          <div>
            <p className="text-sm font-bold tracking-widest gradient-text">ASPIRANT AI</p>
            <p className="text-[11px] text-slate-400">Intelligence Beyond Assistance</p>
          </div>
        </div>

        <nav className="grid grid-cols-2 gap-1.5 sm:grid-cols-4 lg:grid-cols-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelect(item.id)}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all focus:outline-none focus:ring-2 focus:ring-sky-500 ${
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
              </button>
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
        {theme === "dark" ? <Sun className="h-4 w-4 text-sky-400" /> : <Moon className="h-4 w-4 text-violet-500" />}
      </button>
    </aside>
  );
}
