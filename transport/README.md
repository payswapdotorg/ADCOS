# ADCOS Transport — Secure transport profiles (WORK-017)

## Status

**ACTIVE — Module Authority: secure transport mappings**

Implements the WORK-017 Work Item (`spec/work-items.md`) behind the
frozen `/transport` module boundary (`spec/architecture.md` §29;
`spec/architecture-lock.md` module ownership): transport mappings for
secure control/user paths over TLS 1.3, QUIC, and standard IP tunnels,
with session security independent of access technology, keys bound to
session/identity policy, replaceable transports behind the transport
interface, and tested replay/downgrade resistance.

## Authority boundary

```text
SECURE TRANSPORT
    ≠ SESSION AUTHORITY     (read-only WORK-012 lookup via SessionReader)
    ≠ IDENTITY AUTHORITY    (WORK-004 facade; secrets stay in the store)
    ≠ POLICY AUTHORITY      (caller-supplied policy floor DATA)
    ≠ TOPOLOGY AUTHORITY
    ≠ ACCESS AUTHORITY      (siblings with /adapters beneath session
                             semantics — architecture §25 rule 9)
    ≠ VENDOR AUTHORITY      (LOCK-017: engine health is data, never authority)
```

The transport layer is authoritative **only** for the secure-channel
state of the transports it manages — never for ADCOS-wide state.

## The replaceable interface

| Operation | Mediated behavior |
|---|---|
| `supported_profiles()` | profile ids the implementation serves (data) |
| `initialize(context)` | bring up per-transport engine state |
| `handshake_initiator(context, offer)` | start the initiator side (pending handle) |
| `handshake_responder(context, offer, …)` | negotiate, mint the final id, derive keys, produce the acceptance |
| `complete_initiator(context, offer, acceptance, …)` | verify echo/selection/id/confirmation, produce the initiator confirmation |
| `accept_confirmation(context, …)` | verify the initiator key confirmation |
| `protect(context, payload)` | frame + protect one payload (modeled AEAD) |
| `unprotect(context, frame)` | verify integrity/generation/replay, return payload |
| `rekey(context, cause)` | chained generation advance (rotation bound: 8) |
| `health()` | implementation-local health (never authoritative alone) |
| `close(context)` | destroy working key material |

Implementations depend on `TransportContract` + the least-authority
`TransportContext` facade (ids, injected instant, deterministic step
budget) and on nothing else.  `ModeledTransportEngine` — the built-in
deterministic implementation of the initial profiles — uses standard
IETF primitives only (HKDF-SHA256 RFC 5869, HMAC-SHA256); it is a
model of the standard handshake/record structure, not a concrete
network stack.  Concrete production transports (real TLS 1.3/QUIC
libraries, IPsec/WireGuard daemons) plug in behind the same ABC;
`TransportManager.register_implementation` swaps them at runtime.

## Security model (§19; LOCK-022/LOCK-023)

- **Zero trust**: establishments require usable WORK-004 operational
  credentials on both sides; attestations are verified against the
  signer's active credential; revoked/expired credentials fail closed
  (establish, rekey, and `recheck` suspend live transports).
- **Key binding**: traffic secrets derive over a transcript covering
  (session, both NodeIDs, full offered set, selected profile, policy
  floor, responder attestation) — changing any input changes the keys;
  the freshness contributions are the content-derived nonces.
- **Downgrade resistance** (layered): offer-digest echo; selection
  eligibility (offered ∩ known ∩ policy floor); cryptographic key
  confirmation over the transcript-derived secret.
- **Replay protection**: offer-nonce ledger (handshake replay),
  sliding per-transport anti-replay windows (frame replay),
  WORK-003 temporal validation (message expiration).
- **No secret leakage**: working key material lives only inside
  engine instances; every offer/acceptance/confirmation/state/event/
  view is structurally secret-free (deep secret rejection).
- **Failure isolation**: implementation exceptions (including
  `BaseException`) become typed `TransportFailure` **values**; return
  values are contract-validated before entering manager state; the
  deterministic step budget is the hang model.

## Determinism

All instants are injected; ids (`transport_id`, `offer_nonce`,
`event_id`) are content-derived over WORK-003 canonical JSON; profile
negotiation is maximal-rank with lexicographic tie-break (attacker
order-independent); the whole-manager `snapshot()`/
`to_canonical_bytes()` form is byte-stable for a given operation
history.  No wall clock, no randomness, no network.

## Out of scope

Application protocols (WORK-017 out-of-scope statement), concrete
production TLS/QUIC/IPsec network stacks, IP integration (WORK-018),
concrete access technologies (WORK-019..WORK-022, WORK-038), the
WORK-010 policy engine, multipath scheduling (WORK-013), and any
second identity/session/topology authority.

## Verification

`python3 tools/transport_selftest.py` — contract tests, downgrade and
replay attack tests, interoperability tests, key-binding proofs,
authority-boundary audits, and determinism proofs (runs in CI after
the adapter suite).
