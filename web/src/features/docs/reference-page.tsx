/**
 * ReferencePage — the Reference page of the docs IA (the frozen V2
 * design §9): the vocabularies ADCOS talks in — lifecycle states,
 * evidence classes, capability grants and the canonical objects.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. Nothing on this page is invented vocabulary:
 * - the lifecycle states are the backend state vocabulary the design
 *   tokens map tones for (`@/lib/design/tokens` → STATUS_TONES) — a
 *   module-load guard fails if a listed state is not in that registry;
 * - the evidence classes render through the canonical classifier and
 *   badge (evidenceClassKind + EvidenceBadge), with the honest
 *   NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT disclosure for the physical/
 *   network family (mirroring the evidence surface's own constant);
 * - the capability grants are DERIVED from the coverage registry at
 *   render time (each grant with the operations it unlocks);
 * - the object names are the exported resource interfaces of
 *   `@/lib/api/types` (the same frozen pin the education-registry test
 *   carries), each linked to the concepts that surface it.
 */

import Link from "next/link";
import { EvidenceBadge, Status } from "@/components/ui";
import { STATUS_TONES } from "@/lib/design/tokens";
import { COVERAGE } from "@/lib/api/coverage";
import { CONCEPTS } from "@/lib/education";
import { DocsLink, DocsPageFrame, DocsSection } from "./docs-shared";

/** Stable test ids for the reference page. */
export const REFERENCE_PAGE_TEST_IDS = {
  root: "docs-reference-page",
  vocabulary: "docs-reference-vocabulary",
} as const;

/** The exact expected vocabulary sizes (the module-load guard). */
const EXPECTED_CONTRACT_STATE_COUNT = 13;
const EXPECTED_LEASE_STATE_COUNT = 8;
const EXPECTED_OBJECT_COUNT = 12;

/**
 * The contract lifecycle states (the frozen reference lifecycle — the
 * vocabulary STATUS_TONES maps tones for; UPPERCASE like the backend
 * sends them).
 */
const CONTRACT_LIFECYCLE_STATES: readonly string[] = [
  "INTENT",
  "OFFER_SELECTED",
  "CONTRACT_ACTIVE",
  "EXECUTION_ACTIVE",
  "DELIVERY",
  "ASSURED",
  "DEGRADED",
  "USAGE_FINAL",
  "SETTLEMENT_PENDING",
  "SETTLED",
  "TERMINATED",
  "EXPIRED",
  "FAILED",
];

/** The lease lifecycle states (the contracts-domain lowercase vocabulary). */
const LEASE_LIFECYCLE_STATES: readonly string[] = [
  "planned",
  "reserved",
  "granted",
  "active",
  "renewed",
  "revoked",
  "measured",
  "released",
];

/**
 * The canonical object vocabulary — the exported resource interfaces of
 * `@/lib/api/types` (the pin the education-registry test carries; the
 * concepts' relatedObjects resolve against exactly this set).
 */
const OBJECT_VOCABULARY: readonly string[] = [
  "Application",
  "Contract",
  "ContractLifecycle",
  "ContractUsage",
  "ContractAssurance",
  "Lease",
  "WebhookEndpoint",
  "WebhookDelivery",
  "DemoDocument",
  "DemoBoundaryEntry",
  "OpaqueReference",
  "HardConstraint",
];

/* The module-load guard: every listed state must exist in the tone registry, and the pins must hold their frozen sizes. */
{
  for (const state of [...CONTRACT_LIFECYCLE_STATES, ...LEASE_LIFECYCLE_STATES]) {
    if (!(state in STATUS_TONES)) {
      throw new Error(`docs reference page: state "${state}" is not in the backend state vocabulary`);
    }
  }
  if (CONTRACT_LIFECYCLE_STATES.length !== EXPECTED_CONTRACT_STATE_COUNT) {
    throw new Error("docs reference page: the contract lifecycle state pin has drifted");
  }
  if (LEASE_LIFECYCLE_STATES.length !== EXPECTED_LEASE_STATE_COUNT) {
    throw new Error("docs reference page: the lease lifecycle state pin has drifted");
  }
  if (OBJECT_VOCABULARY.length !== EXPECTED_OBJECT_COUNT) {
    throw new Error("docs reference page: the object vocabulary pin has drifted");
  }
}

/** The honest disclosure for the physical/network evidence family (§17, mirroring the evidence surface's own constant). */
const NOT_ACHIEVABLE_BY_THIS_DEPLOYMENT = "NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT";

/** Capability grants DERIVED from the coverage registry (grant → the operations it unlocks). */
function capabilityGrants(): { grant: string; operations: string[] }[] {
  const map = new Map<string, string[]>();
  for (const record of COVERAGE) {
    if (!record.requiredCapability) continue;
    const operations = map.get(record.requiredCapability) ?? [];
    operations.push(record.operation);
    map.set(record.requiredCapability, operations);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([grant, operations]) => ({ grant, operations }));
}

function StateChips({ states }: { states: readonly string[] }) {
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-2">
      {states.map((state) => (
        <Status key={state} value={state} size="sm" />
      ))}
    </p>
  );
}

export function ReferencePage() {
  const grants = capabilityGrants();
  return (
    <DocsPageFrame
      sectionId="reference"
      pageLabel="Reference"
      title="Reference"
      lede="The vocabularies ADCOS talks in. These are frozen on the backend boundary — the console renders them verbatim, and so does this page."
      wide
    >
      <DocsSection
        id="lifecycle-states"
        title="Contract lifecycle states"
        description={`${CONTRACT_LIFECYCLE_STATES.length} states — the contract's journey from a recorded intent to a terminal state. The label is the verbatim backend value.`}
      >
        <StateChips states={CONTRACT_LIFECYCLE_STATES} />
        <p className="text-sm leading-relaxed text-ink-muted">
          The honest markers: <Status value="DEGRADED" size="sm" /> is a
          reported position, never a silent condition;{" "}
          <Status value="TERMINATED" size="sm" />,{" "}
          <Status value="EXPIRED" size="sm" /> and{" "}
          <Status value="FAILED" size="sm" /> are terminal — no further
          commands are accepted. Read the state&apos;s reasoning through the{" "}
          <DocsLink
            link={{ kind: "concept", id: "eligibility", label: "Eligibility concept" }}
          />
          .
        </p>
      </DocsSection>

      <DocsSection
        id="lease-states"
        title="Lease lifecycle states"
        description={`${LEASE_LIFECYCLE_STATES.length} states — a lease's bounded access window over an active contract.`}
      >
        <StateChips states={LEASE_LIFECYCLE_STATES} />
        <p className="text-sm leading-relaxed text-ink-muted">
          Leases are granted, renewed and revoked through the operations
          documented on the{" "}
          <DocsLink link={{ kind: "docs", id: "api", label: "API pages" }} /> —
          renewal moves the prior lease to <Status value="renewed" size="sm" />,
          revocation is terminal.
        </p>
      </DocsSection>

      <DocsSection
        id="evidence-classes"
        title="Evidence classes"
        description="The distinction the whole console protects: software-side evidence never passes as physical/network evidence."
      >
        <ul className="flex flex-col gap-2.5">
          <li className="flex flex-wrap items-baseline gap-2">
            <EvidenceBadge evidenceClass="SOFTWARE" />
            <span className="text-sm text-ink-muted">
              deterministic software-side evidence — what the demonstration
              document&apos;s records carry (rendered verbatim)
            </span>
          </li>
          <li className="flex flex-wrap items-baseline gap-2">
            <EvidenceBadge evidenceClass="sandbox-simulation" />
            <span className="text-sm text-ink-muted">
              simulation-class evidence — the label the sandbox composition
              itself puts on lifecycle, usage and assurance reads
            </span>
          </li>
          <li className="flex flex-wrap items-baseline gap-2">
            <EvidenceBadge evidenceClass="NOT-CLAIMED" />
            <span className="text-sm text-ink-muted">
              the unclaimed family — no evidence class asserted
            </span>
          </li>
          <li className="flex flex-wrap items-baseline gap-2">
            <span className="inline-flex items-center rounded-md border border-solid border-line-strong px-1.5 py-0.5 font-mono text-xs text-ink">
              physical / network
            </span>
            <span className="text-sm text-ink-muted">
              the physical/network family is{" "}
              <span className="font-mono text-xs text-ink">
                {NOT_ACHIEVABLE_BY_THIS_DEPLOYMENT}
              </span>{" "}
              — this deployment produces software-side evidence only, and no
              UI state can ever transform a SOFTWARE record into a physical
              PASS
            </span>
          </li>
        </ul>
        <p className="text-sm leading-relaxed text-ink-muted">
          Read the model behind the classes:{" "}
          <DocsLink link={{ kind: "concept", id: "evidence", label: "Evidence concept" }} />.
        </p>
      </DocsSection>

      <DocsSection
        id="capability-grants"
        title="Capability grants"
        description={`Derived from the coverage registry — each grant with the operations it unlocks (${grants.length} grants; application_self and the platform routes need none).`}
      >
        <dl className="flex flex-col gap-2.5">
          {grants.map((grant) => (
            <div
              key={grant.grant}
              className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3"
            >
              <dt className="break-all font-mono text-xs text-ink">{grant.grant}</dt>
              <dd className="flex flex-wrap items-center gap-x-3 gap-y-1">
                {grant.operations.map((operation) => (
                  <DocsLink
                    key={operation}
                    link={{ kind: "operation", id: operation, label: operation }}
                    className="font-mono text-xs"
                  />
                ))}
              </dd>
            </div>
          ))}
        </dl>
        <p className="text-sm leading-relaxed text-ink-muted">
          An operation without its grant fails with{" "}
          <Link
            href="/docs/errors#code-capability-denied"
            className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted transition-colors hover:border-line-strong hover:text-ink"
          >
            capability-denied
          </Link>
          . The grants your application holds are listed by{" "}
          <DocsLink
            link={{ kind: "concept", id: "application-capability", label: "Application and capability" }}
          />
          .
        </p>
      </DocsSection>

      <DocsSection
        id="objects"
        title="Canonical objects"
        description={`The resource interfaces of the accepted boundary (${OBJECT_VOCABULARY.length} names), each linked to the concepts that surface it.`}
      >
        <dl className="flex flex-col gap-2.5">
          {OBJECT_VOCABULARY.map((objectName) => {
            const concepts = CONCEPTS.filter((concept) =>
              concept.relatedObjects.includes(objectName),
            );
            return (
              <div
                key={objectName}
                data-testid={REFERENCE_PAGE_TEST_IDS.vocabulary}
                data-name={objectName}
                className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3"
              >
                <dt className="break-all font-mono text-xs text-ink">{objectName}</dt>
                <dd className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                  {concepts.length > 0 ? (
                    concepts.map((concept) => (
                      <DocsLink
                        key={concept.id}
                        link={{ kind: "concept", id: concept.id, label: concept.term }}
                      />
                    ))
                  ) : (
                    <span className="text-sm text-ink-faint">
                      surfaced by the API reads it types
                    </span>
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
      </DocsSection>
    </DocsPageFrame>
  );
}
