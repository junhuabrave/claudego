import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default mergeConfig(
  viteConfig,
  defineConfig({
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
  })
);
