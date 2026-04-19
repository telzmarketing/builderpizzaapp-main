import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./client/**/*.{ts,tsx}"],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        /* ── Brand palette — mapped to CSS vars (dynamic via /theme API) ── */
        brand: {
          deep:  "var(--bg-main, #0c1220)",
          dark:  "var(--navbar-bg, #111827)",
          mid:   "var(--border-color, #2d3d56)",
        },
        gold: {
          DEFAULT: "var(--color-primary, #f97316)",
          light:   "var(--interaction-hover, #fb923c)",
          muted:   "#7c2d12",
        },
        cream:     "var(--text-primary, #f8fafc)",
        parchment: "var(--text-secondary, #e2e8f0)",
        stone:     "var(--text-muted, #94a3b8)",
        surface: {
          "00": "var(--bg-main, #0c1220)",
          "01": "var(--bg-alt, #111827)",
          "02": "var(--bg-card, #1e2a3b)",
          "03": "var(--border-color, #2d3d56)",
        },
        /* ── Semantic theme tokens ── */
        theme: {
          primary:   "var(--color-primary, #f97316)",
          secondary: "var(--color-secondary, #2d3d56)",
          "bg-main":  "var(--bg-main, #0c1220)",
          "bg-alt":   "var(--bg-alt, #111827)",
          "bg-card":  "var(--bg-card, #1e2a3b)",
          "text-primary":   "var(--text-primary, #f8fafc)",
          "text-secondary": "var(--text-secondary, #e2e8f0)",
          "text-muted":     "var(--text-muted, #94a3b8)",
          "status-success": "var(--status-success, #22c55e)",
          "status-error":   "var(--status-error, #ef4444)",
          "status-warning": "var(--status-warning, #f59e0b)",
          "status-info":    "var(--status-info, #3b82f6)",
          border:  "var(--border-color, #2d3d56)",
          hover:   "var(--interaction-hover, #fb923c)",
          active:  "var(--interaction-active, #ea6f10)",
          focus:   "var(--interaction-focus, #f97316)",
          navbar:  "var(--navbar-bg, #111827)",
          footer:  "var(--footer-bg, #0c1220)",
          sidebar: "var(--sidebar-bg, #111827)",
          modal:   "var(--modal-bg, #1e2a3b)",
          overlay: "var(--overlay-bg, #000000)",
          badge:   "var(--badge-bg, #f97316)",
          tag:     "var(--tag-bg, #2d3d56)",
        },
        /* ── shadcn tokens ── */
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: {
            height: "0",
          },
          to: {
            height: "var(--radix-accordion-content-height)",
          },
        },
        "accordion-up": {
          from: {
            height: "var(--radix-accordion-content-height)",
          },
          to: {
            height: "0",
          },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
