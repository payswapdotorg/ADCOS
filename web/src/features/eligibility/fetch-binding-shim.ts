/**
 * ⚠️ TEMPORARY COMPATIBILITY SHIM — read me before keeping me. ⚠️
 *
 * ROOT CAUSE (foundation bug, OUTSIDE Worker 2's frozen file surface —
 * disclosed in the console/connectivity completion report):
 *
 *   web/src/lib/api/client.ts
 *     private get doFetch(): typeof fetch {
 *       return this.injectedFetch ?? globalThis.fetch;
 *     }
 *     ...
 *     response = await this.doFetch(path, { ... });
 *
 * Because `doFetch` is a prototype GETTER, the call `this.doFetch(...)`
 * evaluates as a member-call on a Reference whose base is the AdcosClient
 * INSTANCE — the native fetch function is therefore invoked with
 * `this` = the client object, and every real browser's WebIDL binding
 * rejects that with:
 *
 *   TypeError: Failed to execute 'fetch' on 'Window': Illegal invocation
 *
 * The typed client's catch then synthesizes `backend-unreachable`, so
 * EVERY client call (reads AND mutations) fails in real browsers. The
 * suites never caught it because they inject `fetchImpl` (a plain,
 * this-tolerant function) at the transport boundary.
 *
 * THE REAL FIX belongs in the client (the Tech Lead owns it — any one of):
 *   - return a bound reference from the getter:
 *       return this.injectedFetch ?? globalThis.fetch.bind(globalThis);
 *   - or capture before calling:
 *       const fetchFn = this.doFetch;
 *       response = await fetchFn(path, { ... });
 *
 * THIS SHIM keeps the console functional until that fix lands: it
 * installs a this-tolerant bound `fetch` on globalThis (idempotent,
 * semantics-preserving — a normally-called fetch behaves identically;
 * only wrong-`this` invocations stop throwing). Worker 2's pages import
 * this module for its side effect so the binding is in place before any
 * client call they make. DELETE this file (and its imports) when the
 * client fix lands.
 */

export function ensureFetchThisBinding(): void {
  const current: unknown = (globalThis as { fetch?: unknown }).fetch;
  if (typeof current !== "function") return;
  const fn = current as (...args: unknown[]) => unknown;
  // already bound (native bound functions are named "bound <name>") —
  // idempotent across dev HMR re-evaluations
  if (fn.name.startsWith("bound ")) return;
  (globalThis as { fetch?: unknown }).fetch = fn.bind(globalThis);
}

ensureFetchThisBinding();
