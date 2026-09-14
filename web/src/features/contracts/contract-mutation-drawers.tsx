"use client";

/**
 * The contract mutation drawers — Terminate, Grant lease, Renew lease,
 * Revoke lease. Every drawer embeds MutationForm (the ApiRequestPanel
 * preview before submit, the sent request + outcome after, ErrorState
 * with the verbatim reason on failure) and its inputs prefill sensibly
 * INSIDE the contract validity window.
 *
 * Vocabulary rules rendered honestly:
 * - the termination condition select offers EXACTLY the contract's OWN
 *   termination.conditions values (never a frontend-invented vocabulary);
 * - the lease-window rule is explained inline: the window must lie inside
 *   the contract validity window — the backend rejects otherwise with
 *   invalid-input;
 * - only granted/active leases renew/revoke (the backend rejects renewed
 *   with invalid-input "only granted/active leases revoke (found renewed)").
 */

import { useState } from "react";
import type { AdcosEnvelope, Contract, Lease } from "@/lib/api/types";
import { Drawer } from "@/components/ui";
import { useSession } from "@/lib/session";
import { MutationForm, StateOutcome, nowRfc3339 } from "./mutation-form";

const inputClasses =
  "h-8 w-full rounded-md border border-line bg-raised px-2 text-sm text-ink";

/* ------------------------------------------------------------------ */
/* Termination                                                         */
/* ------------------------------------------------------------------ */

export function TerminateDrawer({
  contract,
  onClose,
  onDone,
}: {
  contract: Contract;
  onClose: () => void;
  onDone: (envelope: AdcosEnvelope<Contract>) => void;
}) {
  const { client } = useSession();
  const [condition, setCondition] = useState(contract.termination.conditions[0] ?? "");
  const [reason, setReason] = useState("");
  const [recordedAt] = useState(nowRfc3339);
  const body = { recorded_at: recordedAt, condition, reason };

  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Terminate contract"
      description="POST /api/2.0/contracts/{id}/termination — terminal, with a condition from the contract's own vocabulary"
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm leading-relaxed text-ink-muted">
          Termination is terminal: the contract state becomes TERMINATED and
          accepts no further commands. The condition must come from the
          contract&apos;s own termination vocabulary — the backend rejects any
          other value.
        </p>
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="terminate-condition"
            className="font-mono text-2xs text-ink-faint"
          >
            condition (from the contract&apos;s own termination vocabulary)
          </label>
          <select
            id="terminate-condition"
            value={condition}
            onChange={(event) => setCondition(event.target.value)}
            className={inputClasses}
          >
            {contract.termination.conditions.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="terminate-reason" className="font-mono text-2xs text-ink-faint">
            reason
          </label>
          <input
            id="terminate-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className={inputClasses}
          />
        </div>
        <div>
          <p className="font-mono text-2xs text-ink-faint">recorded_at</p>
          <p className="font-mono text-xs text-ink">{recordedAt}</p>
        </div>
        <MutationForm<Contract>
          path={`/api/2.0/contracts/${contract.id}/termination`}
          body={body}
          confirmLabel="Terminate contract"
          danger
          disabled={contract.termination.conditions.length === 0}
          disabledHint="the contract carries no termination conditions"
          submit={(idempotencyKey) =>
            client.terminateContract(contract.id, body, { idempotencyKey })
          }
          onDone={onDone}
          renderOutcome={(envelope) => <StateOutcome state={envelope.data.state} />}
        />
      </div>
    </Drawer>
  );
}

/* ------------------------------------------------------------------ */
/* Lease grant / renewal                                               */
/* ------------------------------------------------------------------ */

export function LeaseWindowDrawer({
  mode,
  contract,
  lease,
  onClose,
  onDone,
}: {
  mode: "grant" | "renew";
  contract: Contract;
  /** The lease being renewed (absent for grant). */
  lease?: Lease;
  onClose: () => void;
  onDone: (envelope: AdcosEnvelope<Lease>) => void;
}) {
  const { client } = useSession();
  const [grantedAt, setGrantedAt] = useState(
    mode === "grant" ? contract.validity.not_before : nowRfc3339(),
  );
  const [notBefore, setNotBefore] = useState(
    mode === "grant"
      ? contract.validity.not_before
      : (lease?.not_before ?? contract.validity.not_before),
  );
  const [notAfter, setNotAfter] = useState(
    mode === "grant"
      ? contract.validity.not_after
      : (lease?.not_after ?? contract.validity.not_after),
  );
  const body = { granted_at: grantedAt, not_before: notBefore, not_after: notAfter };

  const path =
    mode === "grant"
      ? `/api/2.0/contracts/${contract.id}/leases`
      : `/api/2.0/leases/${lease?.id}/renewal`;

  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={mode === "grant" ? "Grant lease" : "Renew lease"}
      description={
        mode === "grant"
          ? `POST /api/2.0/contracts/{id}/leases on ${contract.id}`
          : `POST /api/2.0/leases/{id}/renewal on ${lease?.id}`
      }
    >
      <div className="flex flex-col gap-4">
        <p
          data-testid="lease-validity-rule"
          role="note"
          className="rounded-md border border-line bg-raised px-3 py-2 text-xs leading-relaxed text-ink-muted"
        >
          The lease window must lie inside the contract validity window
          (not_before{" "}
          <span className="font-mono text-ink">{contract.validity.not_before}</span> …
          not_after{" "}
          <span className="font-mono text-ink">{contract.validity.not_after}</span>) —
          the backend rejects otherwise with{" "}
          <span className="font-mono">invalid-input</span>.
        </p>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="lease-granted-at" className="font-mono text-2xs text-ink-faint">
            granted_at
          </label>
          <input
            id="lease-granted-at"
            value={grantedAt}
            onChange={(event) => setGrantedAt(event.target.value)}
            className={`${inputClasses} font-mono`}
            placeholder="RFC 3339 UTC, e.g. 2026-09-14T01:00:00Z"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="lease-not-before" className="font-mono text-2xs text-ink-faint">
            not_before
          </label>
          <input
            id="lease-not-before"
            value={notBefore}
            onChange={(event) => setNotBefore(event.target.value)}
            className={`${inputClasses} font-mono`}
            placeholder="RFC 3339 UTC"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="lease-not-after" className="font-mono text-2xs text-ink-faint">
            not_after
          </label>
          <input
            id="lease-not-after"
            value={notAfter}
            onChange={(event) => setNotAfter(event.target.value)}
            className={`${inputClasses} font-mono`}
            placeholder="RFC 3339 UTC"
          />
        </div>
        <MutationForm<Lease>
          path={path}
          body={body}
          confirmLabel={mode === "grant" ? "Grant lease" : "Renew lease"}
          submit={(idempotencyKey) =>
            mode === "grant"
              ? client.grantLease(contract.id, body, { idempotencyKey })
              : client.renewLease(lease!.id, body, { idempotencyKey })
          }
          onDone={onDone}
          renderOutcome={(envelope) => <StateOutcome state={envelope.data.state} />}
        />
      </div>
    </Drawer>
  );
}

/* ------------------------------------------------------------------ */
/* Lease revocation                                                    */
/* ------------------------------------------------------------------ */

export function RevokeLeaseDrawer({
  lease,
  onClose,
  onDone,
}: {
  lease: Lease;
  onClose: () => void;
  onDone: (envelope: AdcosEnvelope<Lease>) => void;
}) {
  const { client } = useSession();
  const [reason, setReason] = useState("");
  const [recordedAt] = useState(nowRfc3339);
  const body = { recorded_at: recordedAt, reason };

  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Revoke lease"
      description={`POST /api/2.0/leases/{id}/revocation on ${lease.id}`}
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm leading-relaxed text-ink-muted">
          Revocation is terminal for the lease. Only granted/active leases
          revoke — the backend rejects others with{" "}
          <span className="font-mono">invalid-input</span> (&quot;only
          granted/active leases revoke (found renewed)&quot;).
        </p>
        <dl className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-3 gap-y-1.5">
          <dt className="font-mono text-2xs text-ink-faint">state</dt>
          <dd className="font-mono text-xs text-ink">{lease.state}</dd>
          <dt className="font-mono text-2xs text-ink-faint">window</dt>
          <dd className="font-mono text-xs text-ink">
            {lease.not_before} → {lease.not_after}
          </dd>
        </dl>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="revoke-reason" className="font-mono text-2xs text-ink-faint">
            reason
          </label>
          <input
            id="revoke-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className={inputClasses}
          />
        </div>
        <div>
          <p className="font-mono text-2xs text-ink-faint">recorded_at</p>
          <p className="font-mono text-xs text-ink">{recordedAt}</p>
        </div>
        <MutationForm<Lease>
          path={`/api/2.0/leases/${lease.id}/revocation`}
          body={body}
          confirmLabel="Revoke lease"
          danger
          submit={(idempotencyKey) =>
            client.revokeLease(lease.id, body, { idempotencyKey })
          }
          onDone={onDone}
          renderOutcome={(envelope) => <StateOutcome state={envelope.data.state} />}
        />
      </div>
    </Drawer>
  );
}
