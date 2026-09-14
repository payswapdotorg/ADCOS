"use client";

/**
 * ConsoleSearchProviders — the real search providers for the command
 * palette, mounted on the Worker 3 console pages (Developers surfaces,
 * the API Explorer, the Request Inspector, Evidence, Assurance,
 * Settings).
 *
 * On mount it registers commands into Worker 1's palette infrastructure
 * (and unregisters every one of them on unmount):
 * - CONTRACTS from the fetched list (connected + intents:read): id /
 *   state / principal all match; rows navigate to the contract detail;
 * - WEBHOOK ENDPOINTS from the fetched list (connected + webhooks:read):
 *   rows navigate into the API Explorer with endpoint_get preselected
 *   and the endpoint id prefilled;
 * - EVIDENCE RECORDS from this session's demonstration runs
 *   (useDemoRuns): rows navigate to the Evidence surface;
 * - PLAYBOOKS from the education guide registry (DEC-0128, Task 7):
 *   each of the seven guided paths registers a "Playbook: …" command
 *   navigating to /playbooks/<id> — static registry data, no fetch and
 *   no capability gate (playbooks are education, always reachable);
 * - API EXPLORER OPERATIONS from the coverage registry: read commands
 *   always navigate to /developers/explorer?operation=<operation>;
 *   MUTATION commands appear ONLY when a session is connected AND the
 *   required capability is granted (the application's capability list
 *   is the gate — capabilityGranted); DESTRUCTIVE operations
 *   (termination, lease revocation) require an explicit confirmation
 *   step before even navigating, and the explorer re-confirms before
 *   executing — the backend's own authorization is never bypassed.
 *
 * No provider ever fabricates objects: a failed or ungranted fetch
 * registers nothing (honest absence).
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Contract, WebhookEndpoint } from "@/lib/api/types";
import { COVERAGE, type CoverageRecord } from "@/lib/api/coverage";
import { GUIDES } from "@/lib/education";
import { useSession } from "@/lib/session";
import { capabilityGranted } from "@/features/developers/capabilities";
import { useDemoRuns } from "@/features/evidence/demo-runs";
import { registerCommand } from "./command-registry";
import {
  ApiRequestPanel,
  ConnectivityIcon,
  DevelopersIcon,
  Drawer,
  EvidenceIcon,
} from "@/components/ui";
import { DESTRUCTIVE_OPERATIONS } from "@/features/api-explorer/executor";

/** Short, palette-sized id label (the full id stays in the keywords). */
function shortId(id: string): string {
  return id.length > 16 ? `${id.slice(0, 16)}…` : id;
}

export function ConsoleSearchProviders() {
  const { status, application, client } = useSession();
  const router = useRouter();
  const connected = status === "connected";
  const capabilities = application?.capabilities ?? null;
  const demoRuns = useDemoRuns();

  const [confirmRecord, setConfirmRecord] = useState<CoverageRecord | null>(null);

  const contractsGranted = capabilityGranted("intents:read", capabilities) === true;
  const webhooksGranted = capabilityGranted("webhooks:read", capabilities) === true;

  const [contracts, setContracts] = useState<Contract[]>([]);
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);

  // the fetched object lists — ONLY when the capability is granted; a
  // failed or ungranted fetch leaves the list empty (honest absence)
  useEffect(() => {
    if (!connected || !contractsGranted) {
      setContracts([]);
      return;
    }
    let cancelled = false;
    client
      .listContracts()
      .then((envelope) => {
        if (!cancelled) setContracts(envelope.data.items);
      })
      .catch(() => {
        if (!cancelled) setContracts([]);
      });
    return () => {
      cancelled = true;
    };
  }, [connected, contractsGranted, client]);

  useEffect(() => {
    if (!connected || !webhooksGranted) {
      setEndpoints([]);
      return;
    }
    let cancelled = false;
    client
      .listWebhookEndpoints()
      .then((envelope) => {
        if (!cancelled) setEndpoints(envelope.data.items);
      })
      .catch(() => {
        if (!cancelled) setEndpoints([]);
      });
    return () => {
      cancelled = true;
    };
  }, [connected, webhooksGranted, client]);

  // register the commands (and unregister every one on change/unmount)
  useEffect(() => {
    const unregisters: (() => void)[] = [];

    for (const contract of contracts) {
      unregisters.push(
        registerCommand({
          id: `search-contract-${contract.contract_id}`,
          title: `Contract ${shortId(contract.contract_id)}`,
          keywords: [
            contract.id,
            contract.contract_id,
            contract.state,
            contract.principal.principal_ref,
            "contract",
          ],
          group: "Contracts",
          icon: <ConnectivityIcon className="h-3.5 w-3.5 text-ink-faint" />,
          href: `/connectivity/contracts/${contract.contract_id}`,
        }),
      );
    }

    for (const endpoint of endpoints) {
      unregisters.push(
        registerCommand({
          id: `search-endpoint-${endpoint.id}`,
          title: `Webhook endpoint ${shortId(endpoint.id)}`,
          keywords: [endpoint.id, endpoint.url, ...endpoint.event_types, "webhook"],
          group: "Webhook endpoints",
          icon: <DevelopersIcon className="h-3.5 w-3.5 text-ink-faint" />,
          href: `/developers/explorer?operation=endpoint_get&endpoint_id=${endpoint.id}`,
        }),
      );
    }

    for (const run of demoRuns) {
      unregisters.push(
        registerCommand({
          id: `search-demo-run-${run.instant}`,
          title: `Demo run ${run.instant}`,
          keywords: [
            run.contractId,
            run.instant,
            run.document.evidence_class,
            "evidence",
            "demo",
          ],
          group: "Evidence",
          icon: <EvidenceIcon className="h-3.5 w-3.5 text-ink-faint" />,
          href: "/evidence",
        }),
      );
    }

    // the seven guided paths (DEC-0128, Task 7) — static registry data:
    // every playbook is reachable from any provider-mounted console page
    for (const guide of GUIDES) {
      unregisters.push(
        registerCommand({
          id: `search-playbook-${guide.id}`,
          title: `Playbook: ${guide.title}`,
          keywords: [
            guide.id,
            guide.title,
            guide.purpose,
            ...guide.relatedConcepts,
            "playbook",
            "guide",
            "guided path",
          ],
          group: "Playbooks",
          icon: <EvidenceIcon className="h-3.5 w-3.5 text-ink-faint" />,
          href: `/playbooks/${guide.id}`,
        }),
      );
    }

    for (const record of COVERAGE) {
      // permission-aware: mutation commands require a connected session
      // AND the granted capability — the registry's own requirement
      if (
        record.mutation &&
        !(connected && capabilityGranted(record.requiredCapability, capabilities) === true)
      ) {
        continue;
      }
      const destructive = DESTRUCTIVE_OPERATIONS.has(record.operation);
      const title = record.mutation
        ? `Run ${record.method} ${record.path}${destructive ? " (destructive)" : ""}`
        : `${record.method} ${record.path}`;
      unregisters.push(
        registerCommand({
          id: `search-operation-${record.operation}`,
          title,
          keywords: [record.operation, record.path, record.description, record.requiredCapability],
          group: "API operations",
          icon: <DevelopersIcon className="h-3.5 w-3.5 text-ink-faint" />,
          // destructive operations confirm explicitly BEFORE navigating
          // (the explorer confirms again before executing; the backend
          // re-authorizes every request — nothing is bypassed)
          ...(destructive
            ? { run: () => setConfirmRecord(record) }
            : { href: `/developers/explorer?operation=${record.operation}` }),
        }),
      );
    }

    return () => {
      unregisters.forEach((unregister) => unregister());
    };
  }, [contracts, endpoints, demoRuns, connected, capabilities]);

  return (
    <Drawer
      open={confirmRecord !== null}
      onOpenChange={(open) => {
        if (!open) setConfirmRecord(null);
      }}
      title="Destructive operation"
      description="Explicit confirmation required — destructive operations are never opened from the palette without one."
      footer={
        <>
          <button
            type="button"
            data-testid="destructive-cancel"
            onClick={() => setConfirmRecord(null)}
            className="inline-flex h-8 items-center rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
          >
            Cancel
          </button>
          <button
            type="button"
            data-testid="destructive-continue"
            onClick={() => {
              if (confirmRecord) {
                router.push(`/developers/explorer?operation=${confirmRecord.operation}`);
              }
              setConfirmRecord(null);
            }}
            className="inline-flex h-8 items-center rounded-md bg-danger px-3 text-sm font-medium text-white transition-colors hover:opacity-90"
          >
            Continue to the API Explorer
          </button>
        </>
      }
    >
      {confirmRecord ? (
        <div className="flex flex-col gap-3">
          <ApiRequestPanel
            variant="compact"
            method={confirmRecord.method}
            path={confirmRecord.path}
          />
          <p className="text-sm text-ink-muted">{confirmRecord.description}</p>
          <p className="text-xs text-ink-muted">
            The explorer opens with this operation selected and requires its own
            confirmation before executing; the backend authorizes the request
            itself. This step never bypasses backend authorization.
          </p>
        </div>
      ) : null}
    </Drawer>
  );
}
