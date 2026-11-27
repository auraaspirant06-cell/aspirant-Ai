import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        aspirant: {
          bg: "#05070E",
          surface: "#0B1020",
          elevated: "#111827",
          blue: "#0EA5E9",
          cobalt: "#3B82F6",
          purple: "#8B5CF6",
          indigo: "#6366F1",
        },
      },
      boxShadow: {
        glow: "0 0 36px -10px rgba(14, 165, 233, 0.45), 0 0 28px -12px rgba(139, 92, 246, 0.4)",
      },
      backgroundImage: {
        "aspirant-gradient": "linear-gradient(135deg, #0EA5E9 0%, #3B82F6 45%, #8B5CF6 100%)",
      },
    },
  },
  plugins: [],
};

export default config;
