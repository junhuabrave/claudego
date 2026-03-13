/**
 * Factory that creates the priceStats Web Worker.
 * Isolated into its own module so tests can mock it via moduleNameMapper
 * without babel choking on import.meta.url during coverage instrumentation.
 */
export function createPriceStatsWorker(): Worker {
  return new Worker(new URL("./priceStats.worker.ts", import.meta.url));
}
