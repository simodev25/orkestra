import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  corePlugins: {
    preflight: false, // Désactivé — le reset vient de globals.css
  },
  theme: {
    extend: {
      colors: {
        "ork-bg":       "oklch(0.16 0.004 80 / <alpha-value>)",
        "ork-surface":  "oklch(0.185 0.004 80 / <alpha-value>)",
        "ork-panel":    "oklch(0.21 0.005 80 / <alpha-value>)",
        "ork-panel-2":  "oklch(0.24 0.005 80 / <alpha-value>)",
        "ork-hover":    "oklch(0.225 0.005 80 / <alpha-value>)",
        "ork-border":   "oklch(0.28 0.006 80 / <alpha-value>)",
        "ork-border-2": "oklch(0.33 0.007 80 / <alpha-value>)",
        "ork-dim":      "oklch(0.48 0.006 85 / <alpha-value>)",
        "ork-text":     "oklch(0.96 0.004 85 / <alpha-value>)",
        "ork-text-1":   "oklch(0.82 0.005 85 / <alpha-value>)",
        "ork-muted":    "oklch(0.62 0.006 85 / <alpha-value>)",
        "ork-muted-2":  "oklch(0.48 0.006 85 / <alpha-value>)",
        "ork-green":    "oklch(0.78 0.17 145 / <alpha-value>)",
        "ork-green-dim":"oklch(0.52 0.12 145 / <alpha-value>)",
        "ork-green-bg": "oklch(0.26 0.07 145 / <alpha-value>)",
        "ork-cyan":     "oklch(0.78 0.13 200 / <alpha-value>)",
        "ork-cyan-bg":  "oklch(0.26 0.06 200 / <alpha-value>)",
        "ork-amber":    "oklch(0.82 0.15 75 / <alpha-value>)",
        "ork-amber-bg": "oklch(0.28 0.07 75 / <alpha-value>)",
        "ork-red":      "oklch(0.70 0.19 25 / <alpha-value>)",
        "ork-red-bg":   "oklch(0.26 0.08 25 / <alpha-value>)",
        "ork-purple":   "oklch(0.72 0.12 305 / <alpha-value>)",
        "ork-purple-bg":"oklch(0.26 0.06 305 / <alpha-value>)",
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
