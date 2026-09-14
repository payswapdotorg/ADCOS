/**
 * Presentation-only formatting helpers for the Home dashboard.
 *
 * NOTHING here transforms backend meaning: truncation is display-only
 * (the full value always travels in the `title` attribute), and link
 * extraction maps a developer-API path to the console's detail route for
 * the SAME backend-minted identifier — never an invented one.
 */

/** Truncate a long backend identifier for dense display (full value in `title`). */
export function truncateId(id: string, keep = 20): string {
  return id.length > keep ? `${id.slice(0, keep)}…` : id;
}

/**
 * The console detail route for a logged API path, when an identifier is
 * extractable. Honest by construction: list calls (no id) link nowhere,
 * and lease entries link nowhere either — leases have no standalone
 * detail route (they are surfaced inside their contract's detail page,
 * and the log entry carries no contract id to link through).
 */
export function detailHrefForPath(path: string): string | null {
  const contractMatch = /\/api\/2\.0\/contracts\/([A-Za-z0-9:_-]+)/.exec(path);
  if (contractMatch) {
    return `/connectivity/contracts/${contractMatch[1]}`;
  }
  return null;
}
