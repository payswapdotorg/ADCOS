# ADCOS Identity Package — WORK-004

## Status

**ACTIVE — Cryptographic Node Identity and Credential Abstraction**

Implements durable, access-independent node identity per
`spec/architecture.md` §6.2/§22 and the machine-readable identity-profile
registry (`spec/schemas/registries/identity-profile-registry.json`).

**No trust policy, authorization policy, federation, discovery, topology,
sessions, adapters, or access technology is implemented here.** Possessing
a valid identity is not trust (LOCK-022).

## The identity boundary

```text
NodeID = durable identity reference
  = SHA-256(domain-separation ‖ profile_id ‖ STABLE identity public key)
  ≠ public key bytes, certificate, SIM/IMSI, modem id, MAC, vendor account,
    IP address, access technology, or a trust decision

Operational keys rotate independently — rotation NEVER changes NodeID
Credential references are opaque; secrets live ONLY in the CredentialStore
Identity profiles are explicit metadata; providers are replaceable
```

NodeID canonical text form: `adcos:node:<profile_id>:<64 lowercase hex>`
(one canonical representation; round-trips without ambiguity; safe to
publish). The profile id is embedded so cryptographic choices are explicit
metadata and future derivation profiles can be added without rewriting
identity-consuming code.

## Module map

```text
identity/
  node_id.py        NodeID derivation, canonical form, fail-closed parsing
  profiles.py       IdentityProfile + registry loader + deterministic negotiation
  lifecycle.py      PROVISIONED/ACTIVE/ROTATING/SUPERSEDED/REVOKED/EXPIRED
  credentials.py    CredentialReference (opaque) + CredentialRecord (public metadata only)
  revocation.py     RevocationInfo (distinct from expiry)
  store.py          CredentialStore interface + atomic commit_batch + dev store (only secret holder)
  provider.py       SignatureProvider abstraction + DevHmacSha256Provider (TEST-ONLY)
  model.py          NodeIdentity, IdentityService (atomic rotation, revocation, destruction)
  serialization.py  public metadata via the WORK-003 canonicalization/envelope
```

## Key semantics

- **Rotation is atomic and authorized**: the identity-role credential
  signs the canonical rotation statement (WORK-003 canonicalization);
  every transition is validated in memory, and the whole rotation commits
  as ONE atomic store transaction (`CredentialStore.commit_batch`) — a
  failure at validation, authorization, OR the storage boundary leaves
  the previous credential active with no leaked record/secret (no
  half-state). The current role credential and the authorizing identity
  credential are both validated against the actual rotation instant, so
  an expired credential can neither be rotated nor authorize a rotation.
- **Revocation ≠ expiry**: revocation is an explicit act with metadata;
  expiry is time-based. Both fail closed (no reactivation, no secret
  selection); revoked secrets are not selectable through the store.
- **Destroy is explicit**: `destroy_identity()` revokes every credential
  and blocks new provisioning; NodeID and records remain queryable for
  history. Nothing else ends an identity's operability.
- **Algorithm agility**: profiles and providers declare algorithm
  identifiers as data; the core only compares declarations — never
  branches on an algorithm. Negotiation is deterministic (sorted
  mutual intersection; disjoint → error). Unknown profile identifiers
  (e.g. `identity.future.example-v1`) are UNKNOWN: preserved verbatim,
  never coerced, fail closed on use.
- **Secret isolation**: public types are structurally secret-free; the
  ONLY secret access path is `CredentialStore.get_secret(reference)`.
  Verified by test across metadata, envelope bytes, reprs, and exception
  messages.

## Cryptographic notes

NodeID derivation uses SHA-256 (standard primitive, domain-separated,
declared in the registry). Signing goes through the replaceable
`SignatureProvider`; `DevHmacSha256Provider` implements the
**development/test-only** `alg.hmac-sha256.dev` algorithm so the full
lifecycle is deterministic and offline (HMAC is symmetric — its public
material is a key fingerprint and external public verification is not
possible; documented in the registry). Real deployments use asymmetric
providers (Ed25519, ECDSA P-256) for the corresponding registered
profiles. No cryptographic algorithm is invented here.

## Verification

```bash
python3 tools/identity_selftest.py   # 17 deterministic cases
```

CI runs this suite together with all prior suites. All test key material
is fixed TEST-ONLY bytes; all clocks are injected RFC 3339 UTC strings.
