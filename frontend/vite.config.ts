import { execSync } from "child_process";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const gitSha = (() => {
  try {
    return execSync("git rev-parse --short HEAD").toString().trim();
  } catch {
    return "dev";
  }
})();
const buildDate = new Date().toISOString().slice(0, 10); // YYYY-MM-DD

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(`${buildDate} (${gitSha})`),
  },
  plugins: [react()],
  server: {
    port: 3000,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom"],
          "vendor-mui": [
            "@mui/material",
            "@mui/icons-material",
            "@mui/x-date-pickers",
            "@emotion/react",
            "@emotion/styled",
          ],
          "vendor-query": ["@tanstack/react-query"],
          "vendor-i18n": ["i18next", "react-i18next"],
          "vendor-google": ["@react-oauth/google"],
        },
      },
    },
  },
});
