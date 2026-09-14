"use client";

/**
 * The state-advancing action cards — the work order drives the contract
 * lifecycle mutations from the UI:
 *
 * - INTENT        → "Next step · Accept offers"   (POST /api/2.0/intents/{id}/offers)
 * - OFFER_SELECTED → "Next step · Activate contract" (POST /api/2.0/intents/{id}/activation)
 *
 * Both cards embed MutationForm: the ApiRequestPanel preview is visible
 * before submit, the sent request + outcome (new state through Status)
 * after, and failures surface the backend's verbatim reason through
 * ErrorState. Offer and signature material is opaque typed references —
 * the console never interprets them.
 */

import { useState } from "react";
import type { AcceptOffersInput, ActivateContractInput, AdcosEnvelope, Contract } from "@/lib/api/types";
import { ObjectSection } from "@/features/eligibility";
import { useSession } from "@/lib/session";
import { MutationForm, StateOutcome, nowRfc3339 } from "./mutation-form";

const inputClasses =
  "h-8 w-full rounded-md border border-line bg-raised px-2 text-sm text-ink";

const removeButtonClasses =
  "inline-flex h-7 shrink-0 items-center rounded-md border border-line px-2 text-xs text-ink-muted transition-colors hover:text-ink";

const addButtonClasses =
  "inline-flex h-7 items-center self-start rounded-md border border-line px-2 text-xs text-ink-muted transition-colors hover:text-ink";

/* ------------------------------------------------------------------ */
/* Accept offers (INTENT → OFFER_SELECTED)                             */
/* ------------------------------------------------------------------ */

interface OfferDraft {
  value: string;
  issuer: string;
  decisionRefs: string;
}

/** Seeds from the canonical demo offer (the coverage registry example). */
const DEFAULT_OFFER: OfferDraft = {
  value: "demo:offer:ran-reference:v1",
  issuer: "provider:ran-reference",
  decisionRefs: "demo:offer:v1",
};

function splitCommaList(raw: string): string[] {
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

export function AcceptOffersCard({
  contract,
  onDone,
}: {
  contract: Contract;
  onDone: (envelope: AdcosEnvelope<Contract>) => void;
}) {
  const { client } = useSession();
  const [offers, setOffers] = useState<OfferDraft[]>([{ ...DEFAULT_OFFER }]);
  const [recordedAt] = useState(nowRfc3339);

  const body: AcceptOffersInput = {
    recorded_at: recordedAt,
    offers: offers
        .filter((offer) => offer.value.trim().length > 0)
        .map((offer) => ({
          ref_kind: "offer",
          value: offer.value,
          provenance: {
            issuer: offer.issuer,
            decision_refs: splitCommaList(offer.decisionRefs),
          },
        })),
  };
  const hasOffers = body.offers.length > 0;

  return (
    <ObjectSection
      id="next-step"
      title="Next step · Accept offers"
      description="Accepting opaque typed offer references moves the contract INTENT → OFFER_SELECTED."
    >
      <div className="flex flex-col gap-3">
        <ul className="flex flex-col gap-2">
          {offers.map((offer, index) => (
            <li
              key={`offer-${index}`}
              className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-raised px-2.5 py-2"
            >
              <input
                aria-label={`offer ${index + 1} value`}
                value={offer.value}
                onChange={(event) =>
                  setOffers((previous) =>
                    previous.map((item, itemIndex) =>
                      itemIndex === index
                        ? { ...item, value: event.target.value }
                        : item,
                    ),
                  )
                }
                placeholder="offer reference value"
                className={`${inputClasses} min-w-[14rem] flex-1 font-mono`}
              />
              <input
                aria-label={`offer ${index + 1} issuer`}
                value={offer.issuer}
                onChange={(event) =>
                  setOffers((previous) =>
                    previous.map((item, itemIndex) =>
                      itemIndex === index
                        ? { ...item, issuer: event.target.value }
                        : item,
                    ),
                  )
                }
                placeholder="issuer"
                className={`${inputClasses} w-44 font-mono`}
              />
              <input
                aria-label={`offer ${index + 1} decision_refs (comma-separated)`}
                value={offer.decisionRefs}
                onChange={(event) =>
                  setOffers((previous) =>
                    previous.map((item, itemIndex) =>
                      itemIndex === index
                        ? { ...item, decisionRefs: event.target.value }
                        : item,
                    ),
                  )
                }
                placeholder="decision_refs (comma-separated)"
                className={`${inputClasses} w-56 font-mono`}
              />
              <button
                type="button"
                aria-label={`Remove offer ${index + 1}`}
                onClick={() =>
                  setOffers((previous) =>
                    previous.filter((_, itemIndex) => itemIndex !== index),
                  )
                }
                className={removeButtonClasses}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={() => setOffers((previous) => [...previous, { ...DEFAULT_OFFER }])}
          className={addButtonClasses}
        >
          Add offer
        </button>
        <div>
          <p className="font-mono text-2xs text-ink-faint">
            recorded_at · ref_kind <span className="text-ink-muted">offer</span> (fixed)
          </p>
          <p className="font-mono text-xs text-ink">{recordedAt}</p>
        </div>
        <MutationForm<Contract>
          path={`/api/2.0/intents/${contract.id}/offers`}
          body={body}
          confirmLabel="Accept offers"
          disabled={!hasOffers}
          disabledHint="at least one offer reference with a value is required"
          submit={(idempotencyKey) =>
            client.acceptOffers(contract.id, body, { idempotencyKey })
          }
          onDone={onDone}
          renderOutcome={(envelope) => <StateOutcome state={envelope.data.state} />}
        />
      </div>
    </ObjectSection>
  );
}

/* ------------------------------------------------------------------ */
/* Activate contract (OFFER_SELECTED → CONTRACT_ACTIVE)                */
/* ------------------------------------------------------------------ */

interface SignatureDraft {
  value: string;
}

export function ActivateCard({
  contract,
  onDone,
}: {
  contract: Contract;
  onDone: (envelope: AdcosEnvelope<Contract>) => void;
}) {
  const { client } = useSession();
  const [signatures, setSignatures] = useState<SignatureDraft[]>([
    { value: "demo:signature:v1" },
  ]);
  const [activatedAt, setActivatedAt] = useState(nowRfc3339);

  const body: ActivateContractInput = {
    activated_at: activatedAt,
    signature_refs: signatures
      .filter((signature) => signature.value.trim().length > 0)
      .map((signature) => ({ ref_kind: "signature", value: signature.value })),
  };
  const hasSignatures = body.signature_refs.length > 0;

  return (
    <ObjectSection
      id="next-step"
      title="Next step · Activate contract"
      description="Activating with signature references moves the contract OFFER_SELECTED → CONTRACT_ACTIVE."
    >
      <div className="flex flex-col gap-3">
        <ul className="flex flex-col gap-2">
          {signatures.map((signature, index) => (
            <li
              key={`signature-${index}`}
              className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-raised px-2.5 py-2"
            >
              <input
                aria-label={`signature ${index + 1} value`}
                value={signature.value}
                onChange={(event) =>
                  setSignatures((previous) =>
                    previous.map((item, itemIndex) =>
                      itemIndex === index
                        ? { ...item, value: event.target.value }
                        : item,
                    ),
                  )
                }
                placeholder="signature reference value"
                className={`${inputClasses} min-w-[14rem] flex-1 font-mono`}
              />
              <button
                type="button"
                aria-label={`Remove signature ${index + 1}`}
                onClick={() =>
                  setSignatures((previous) =>
                    previous.filter((_, itemIndex) => itemIndex !== index),
                  )
                }
                className={removeButtonClasses}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={() => setSignatures((previous) => [...previous, { value: "" }])}
          className={addButtonClasses}
        >
          Add signature
        </button>
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="activate-activated-at"
            className="font-mono text-2xs text-ink-faint"
          >
            activated_at · ref_kind{" "}
            <span className="text-ink-muted">signature</span> (fixed)
          </label>
          <input
            id="activate-activated-at"
            value={activatedAt}
            onChange={(event) => setActivatedAt(event.target.value)}
            className={`${inputClasses} font-mono`}
            placeholder="RFC 3339 UTC"
          />
        </div>
        <MutationForm<Contract>
          path={`/api/2.0/intents/${contract.id}/activation`}
          body={body}
          confirmLabel="Activate contract"
          disabled={!hasSignatures}
          disabledHint="at least one signature reference with a value is required"
          submit={(idempotencyKey) =>
            client.activateContract(contract.id, body, { idempotencyKey })
          }
          onDone={onDone}
          renderOutcome={(envelope) => <StateOutcome state={envelope.data.state} />}
        />
      </div>
    </ObjectSection>
  );
}
