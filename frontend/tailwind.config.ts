import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  corePlugins: {
    preflight: false, // Désactivé — le reset vient de globals.css
  },
  theme: {
    extend: {
      colors: {
        "ork-bg":       "var(--ork-bg)",
        "ork-surface":  "var(--ork-surface)",
        "ork-panel":    "var(--ork-panel)",
        "ork-panel-2":  "var(--ork-panel-2)",
        "ork-hover":    "var(--ork-hover)",
        "ork-border":   "var(--ork-border)",
        "ork-border-2": "var(--ork-border-2)",
        "ork-dim":      "var(--ork-dim)",
        "ork-text":     "var(--ork-text)",
        "ork-text-1":   "var(--ork-text-1)",
        "ork-muted":    "var(--ork-muted)",
        "ork-muted-2":  "var(--ork-muted-2)",
        "ork-green":    "var(--ork-green)",
        "ork-green-dim":"var(--ork-green-dim)",
        "ork-green-bg": "var(--ork-green-bg)",
        "ork-cyan":     "var(--ork-cyan)",
        "ork-cyan-bg":  "var(--ork-cyan-bg)",
        "ork-amber":    "var(--ork-amber)",
        "ork-amber-bg": "var(--ork-amber-bg)",
        "ork-red":      "var(--ork-red)",
        "ork-red-bg":   "var(--ork-red-bg)",
        "ork-purple":   "var(--ork-purple)",
        "ork-purple-bg":"var(--ork-purple-bg)",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      keyframes: {
        fadeIn:    { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp:   { from: { opacity: "0", transform: "translateY(2px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        pulseSlow: { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.55" } },
      },
      animation: {
        "fade-in": "fadeIn 0.2s ease-out",
        "slide-up": "slideUp 0.2s ease-out",
        "pulse-slow": "pulseSlow 3s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
