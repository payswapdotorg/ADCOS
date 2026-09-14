/**
 * Networks feature (Worker 2 — plan Task 6: networks + eligibility + policy).
 *
 * Provider/adapter identity, capabilities, eligibility-relevant facts and
 * provider-owned boundaries (labeled explicitly — never an ADCOS-owned
 * universal topology). Placeholder barrel until Worker 2 lands it.
 */

export const NETWORKS_FEATURE = {
  area: "networks",
  route: "/networks",
  owner: "worker-2",
  notes: [
    "provider-owned topology data must be labeled explicitly",
    "unknown/degraded provider states must be explicit",
    "no fake production network data — empty states when backend is empty",
  ],
} as const;
