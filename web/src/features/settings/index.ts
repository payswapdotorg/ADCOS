/**
 * Settings feature (Worker 3 — Part C).
 *
 * The console-local concerns: appearance (the theme preference — the
 * only persisted setting, never a secret), environment & health (the
 * full /readyz and /healthz documents with the honest liveness vs
 * readiness semantics), the session (application summary + disconnect +
 * the credential policy), and about (the console's own boundary
 * statement). The error workbench lives at /settings/errors
 * (features/errors).
 */

export { Section } from "./section";
export { AppearancePanel } from "./appearance-panel";
export {
  HealthPanel,
  HEALTH_PANEL_TEST_IDS,
} from "./health-panel";
export {
  SessionPanel,
  SESSION_PANEL_TEST_IDS,
} from "./session-panel";
export { AboutPanel, ABOUT_PANEL_TEST_ID } from "./about-panel";

export const SETTINGS_FEATURE = {
  area: "settings",
  route: "/settings",
  owner: "worker-3",
} as const;
