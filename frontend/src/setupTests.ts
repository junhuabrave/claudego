import "@testing-library/jest-dom";

// Polyfill crypto.randomUUID for Jest / JSDOM environments
// (Node < 19 and JSDOM do not expose it as a global)
if (typeof crypto === "undefined" || typeof crypto.randomUUID === "undefined") {
  const nodeCrypto = require("crypto");
  Object.defineProperty(globalThis, "crypto", {
    value: {
      randomUUID: () => nodeCrypto.randomUUID(),
      getRandomValues: (arr: Uint8Array) => nodeCrypto.getRandomValues(arr),
    },
    writable: true,
  });
}
