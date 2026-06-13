/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0F172A",
        surface: "#1E293B",
        "text-primary": "#F1F5F9",
        "text-secondary": "#94A3B8",
        accent: "#3B82F6",
        match: "#DC2626",
        review: "#D97706",
        cleared: "#16A34A",
        cluster: "#7C3AED",
        pending: "#6B7280",
        info: "#2563EB",
        ubo: "#EA580C",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
