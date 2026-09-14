import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

beforeEach(() => {
  // jsdom has no clipboard in CI-like environments; stub the primitives
  // individual suites override these when they need specific behavior
  if (!navigator.clipboard) {
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
        readText: vi.fn().mockResolvedValue(""),
      },
      configurable: true,
    });
  }
  // crypto.randomUUID exists in Node 20+; jsdom polyfills it via Node's
  // global — assert it so idempotency-key tests stay honest
  if (typeof globalThis.crypto?.randomUUID !== "function") {
    Object.defineProperty(globalThis.crypto, "randomUUID", {
      value: () => "00000000-0000-4000-8000-000000000000",
    });
  }
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/");
});
