import "@testing-library/jest-dom";
import "./i18n"; // initialise translations so t() returns real strings in tests

// Polyfill crypto.randomUUID — Node ≥ 19 and modern JSDOM expose it natively;
// older Node and the vitest jsdom environment may not.
if (typeof globalThis.crypto?.randomUUID === "undefined") {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const nodeCrypto = require("crypto");
  Object.defineProperty(globalThis, "crypto", {
    value: {
      randomUUID: () => nodeCrypto.randomUUID() as string,
      getRandomValues: <T extends ArrayBufferView>(arr: T): T =>
        nodeCrypto.getRandomValues(arr) as T,
    },
    writable: true,
    configurable: true,
  });
}

// jsdom 26 introduced file-backed localStorage. When vitest passes an invalid
// --localstorage-file path the resulting stub omits .clear() and .length.
// Override with a guaranteed in-memory implementation so tests always work.
if (typeof localStorage === "undefined" || typeof localStorage.clear !== "function") {
  const _store = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    value: {
      getItem: (key: string) => _store.get(key) ?? null,
      setItem: (key: string, value: string) => _store.set(key, String(value)),
      removeItem: (key: string) => _store.delete(key),
      clear: () => _store.clear(),
      get length() {
        return _store.size;
      },
      key: (index: number) => Array.from(_store.keys())[index] ?? null,
    },
    writable: true,
    configurable: true,
  });
}
