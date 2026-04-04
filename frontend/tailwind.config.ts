import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        ork: {
          bg: "#08080c",
          surface: "#111118",
          panel: "#1a1a24",
          border: "#252530",
          hover: "#2a2a38",
          cyan: "#00d4ff",
          "cyan-dim": "#0a3a4a",
          green: "#10b981",
          amber: "#f59e0b",
          red: "#ef4444",
          purple: "#a78bfa",
          text: "#e4e4e7",
          muted: "#71717a",
          dim: "#3f3f50",
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', "monospace"],
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
