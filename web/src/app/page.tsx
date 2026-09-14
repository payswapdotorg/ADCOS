"use client";

/**
 * Home — placeholder surface for Worker 2 (plan Task 4).
 *
 * The frozen UX spec defines what Home must answer immediately:
 * what connectivity is managed, whether ADCOS is healthy, what is
 * changing, and what needs attention. Worker 2 replaces the content
 * map below with real, linked summaries (no vanity KPIs).
 */

const CONTENT_MAP: { title: string; description: string }[] = [
  {
    title: "Contract health",
    description:
      "Managed connectivity contracts by lifecycle state, each row linked to the contract detail.",
  },
  {
    title: "Active fulfillment",
    description:
      "Currently executing contract→plan→execution chains with their latest milestones.",
  },
  {
    title: "Degraded providers / backends",
    description:
      "Backend and provider states from /readyz and observed health, with degraded states visible.",
  },
  {
    title: "Recent activity",
    description:
      "Latest API activity linked to the underlying resource and request inspector.",
  },
  {
    title: "Action-required items",
    description:
      "Attention-worthy states (degraded, failed, revoked, expiring) linked to their objects.",
  },
  {
    title: "Environment state",
    description:
      "Mode and environment from backend readiness — never a local assumption.",
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Home</h1>
        <p className="mt-1 text-sm text-ink-muted">
          This area is being implemented (Worker 2 — Home + system health).
        </p>
      </header>

      <section aria-labelledby="home-content-map" className="rounded-md border border-line bg-surface">
        <h2
          id="home-content-map"
          className="border-b border-line px-4 py-3 text-sm font-semibold"
        >
          Intended content map (from the frozen UX spec)
        </h2>
        <ul className="divide-y divide-line">
          {CONTENT_MAP.map((entry) => (
            <li key={entry.title} className="px-4 py-3">
              <p className="text-sm font-medium">{entry.title}</p>
              <p className="mt-0.5 text-sm text-ink-muted">{entry.description}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
