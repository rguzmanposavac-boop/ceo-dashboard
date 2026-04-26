import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
    "./stores/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary:   "#0a0e1a",
          secondary: "#0f1b30",
          card:      "#111e35",
        },
        border: "#1e3050",
        accent: {
          blue:   "#5ba4ff",
          green:  "#3de88a",
          yellow: "#f5c542",
          orange: "#ff8c42",
          red:    "#ff5e5e",
        },
        text: {
          primary:   "#e0e6f0",
          secondary: "#7090b0",
          muted:     "#3a5070",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
