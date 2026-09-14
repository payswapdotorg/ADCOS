"use client";

/**
 * CapabilityChips — every capability on the application record, each
 * with its one-line explanation, PLUS the distinct denied
 * presentation for capabilities the registry requires but the
 * application LACKS (work order deliverable #2).
 *
 * The dictionary is the FROZEN module `capabilities.ts`
 * (`capabilityLabel`, `explainCapability`, `requiredCapabilities`) —
 * never a frontend-invented explanation. A denied chip names what the
 * capability unlocks and states the honest consequence: an API call
 * requiring it fails with `capability-denied`, which names the
 * required capability VERBATIM.
 */

import {
  capabilityGranted,
  capabilityLabel,
  explainCapability,
  requiredCapabilities,
} from "./capabilities";
import type { Application } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function CapabilityChips({ application }: { application: Application }) {
  // the record's own order for granted capabilities (verbatim list)
  const granted = application.capabilities;
  // registry-required capabilities missing from the record
  const missing = requiredCapabilities().filter(
    (capability) => !granted.includes(capability),
  );

  return (
    <section
      data-testid="capability-chips"
      className="rounded-md border border-line bg-surface"
    >
      <header className="border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">Capabilities</h2>
        <p className="mt-0.5 text-sm text-ink-muted">
          The effective grants on the application record (
          {granted.length} granted
          {missing.length > 0 ? `, ${missing.length} required and missing` : ""}
          ). Each explanation is derived from the console operation registry —
          what the capability unlocks over the API.
        </p>
      </header>
      <ul className="grid gap-3 p-4 md:grid-cols-2">
        {granted.map((capability) => (
          <CapabilityChip
            key={capability}
            capability={capability}
            granted={capabilityGranted(capability, granted) === true}
          />
        ))}
        {missing.map((capability) => (
          <CapabilityChip
            key={capability}
            capability={capability}
            granted={false}
          />
        ))}
      </ul>
    </section>
  );
}

function CapabilityChip({
  capability,
  granted,
}: {
  capability: string;
  granted: boolean;
}) {
  return (
    <li
      data-testid="capability-chip"
      data-capability={capability}
      data-granted={granted ? "true" : "false"}
      className={cn(
        "flex flex-col gap-1.5 rounded-md border p-3",
        granted
          ? "border-line bg-raised"
          : "border-dashed border-danger/60 bg-danger/5",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <code
          className={cn(
            "rounded border px-1.5 py-px font-mono text-2xs",
            granted
              ? "border-line-strong text-ink-muted"
              : "border-danger/60 text-danger",
          )}
        >
          {capability}
        </code>
        <span className="text-sm font-medium text-ink">
          {capabilityLabel(capability)}
        </span>
        {granted ? (
          <span className="ml-auto font-mono text-2xs text-positive">
            granted
          </span>
        ) : (
          <span className="ml-auto font-mono text-2xs text-danger">
            not granted
          </span>
        )}
      </div>
      <p className="text-xs leading-relaxed text-ink-muted">
        {explainCapability(capability)}
      </p>
      {granted ? null : (
        <p className="text-xs leading-relaxed text-ink-muted">
          Unlocks exactly the operations above. Any API call that requires it
          fails with{" "}
          <span className="font-mono text-ink">capability-denied</span>, which
          names the required capability verbatim.
        </p>
      )}
    </li>
  );
}
