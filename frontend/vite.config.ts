import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
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
  test: {
    globals: true,
    environment: "jsdom",
    pool: "threads",
    setupFiles: "./src/setupTests.ts",
    alias: [
      {
        find: /.*\/workers\/createPriceStatsWorker$/,
        replacement: resolve(__dirname, "src/__mocks__/createPriceStatsWorker.ts"),
      },
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
    },
  },
});
