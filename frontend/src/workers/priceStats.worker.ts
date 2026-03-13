// Web Worker: computes SMA overlays for the stock chart on a background thread.
// Offloads moving-average computation from the main thread (Phase 3 requirement).

import type { CandlePoint } from "../types";

export interface EnhancedCandlePoint extends CandlePoint {
  sma5?: number;
  sma20?: number;
}

interface WorkerInput {
  candles: CandlePoint[];
}

// Minimal worker scope type — avoids requiring "webworker" in tsconfig lib.
interface WorkerScope {
  onmessage: ((e: MessageEvent) => void) | null;
  postMessage: (data: unknown) => void;
}

function computeSMA(values: number[], period: number): (number | undefined)[] {
  return values.map((_, i) => {
    if (i < period - 1) return undefined;
    const slice = values.slice(i - period + 1, i + 1);
    return slice.reduce((a, b) => a + b, 0) / period;
  });
}

const workerSelf = globalThis as unknown as WorkerScope;

workerSelf.onmessage = (e: MessageEvent<WorkerInput>) => {
  const { candles } = e.data;
  const closes = candles.map((c) => c.c);
  const sma5 = computeSMA(closes, 5);
  const sma20 = computeSMA(closes, 20);

  const enhanced: EnhancedCandlePoint[] = candles.map((c, i) => ({
    ...c,
    sma5: sma5[i],
    sma20: sma20[i],
  }));

  workerSelf.postMessage(enhanced);
};
