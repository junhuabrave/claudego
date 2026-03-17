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
