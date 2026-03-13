class MockWorker {
  onmessage: ((e: MessageEvent) => void) | null = null;
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  postMessage(_data: unknown): void {}
  terminate(): void {}
}

export function createPriceStatsWorker(): Worker {
  return new MockWorker() as unknown as Worker;
}
