"""Identity profiles: explicit metadata, registry-backed, negotiated.

Profiles are data (spec/schemas/registries/identity-profile-registry.json),
never hidden implementation conventions. A profile declares:

- profile_id (stable identifier);
- NodeID derivation rule (e.g. sha256-domain-v1, with domain separation);
- key roles (identity / operational);
- supported signing algorithms (stable identifiers, provider-implemented);
- status.

Unknown well-formed profile identifiers are UNKNOWN (preserved verbatim,
never coerced, fail closed on use) — mirroring the WORK-002 unknown-ID
semantics. Malformed identifiers are INVALID.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_REGISTRY_PATH = REPO_ROOT / "spec" / "schemas" / "registries" / "identity-profile-registry.json"


class ProfileError(ValueError):
    """Raised for unknown/invalid profiles or failed negotiation."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _load_json_no_duplicates(text: str) -> object:
    def hook(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProfileError("registry", "duplicate key %r in identity-profile registry" % key)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=hook)


@dataclass(frozen=True)
class IdentityProfile:
    """A registered (or explicitly supplied) identity profile."""

    profile_id: str
    derivation: str
    domain_separation: str
    key_roles: Tuple[str, ...]
    signing_algorithms: Tuple[str, ...]
    status: str
    description: str = ""

    def supports_role(self, role: str) -> bool:
        return role in self.key_roles

    def supports_algorithm(self, algorithm: str) -> bool:
        return algorithm in self.signing_algorithms

    def __repr__(self) -> str:  # data-only; no secrets by construction
        return "IdentityProfile(profile_id=%r, derivation=%r, roles=%r, algorithms=%r, status=%r)" % (
            self.profile_id,
            self.derivation,
            list(self.key_roles),
            list(self.signing_algorithms),
            self.status,
        )


class ProfileSet:
    """The set of profiles available to an identity consumer.

    The default set loads the machine-readable registry; callers may
    also supply explicit additional profiles (for tests and future
    registered profiles) — but unknown registry identifiers remain
    unknown and fail closed for operations.
    """

    def __init__(self, profiles: Mapping[str, IdentityProfile], grammar: str) -> None:
        self._profiles: Dict[str, IdentityProfile] = dict(profiles)
        self._grammar = grammar

    @classmethod
    def load_default(cls) -> "ProfileSet":
        registry = cast(Dict[str, object], _load_default_registry())
        entries = cast(Mapping[str, Mapping[str, object]], registry.get("entries", {}))
        derivation_rules = cast(Mapping[str, Mapping[str, object]], registry.get("derivation_rules", {}))
        profiles: Dict[str, IdentityProfile] = {}
        for profile_id, raw_entry in entries.items():
            entry = cast(Mapping[str, object], raw_entry)
            rule = cast(
                Mapping[str, object],
                derivation_rules.get(cast(str, entry.get("derivation")), {}),
            )
            profiles[profile_id] = IdentityProfile(
                profile_id=profile_id,
                derivation=cast(str, entry["derivation"]),
                domain_separation=cast(str, rule.get("domain_separation", "")),
                key_roles=tuple(cast(Sequence[str], entry.get("key_roles", ()))),
                signing_algorithms=tuple(cast(Sequence[str], entry.get("signing_algorithms", ()))),
                status=cast(str, entry.get("status", "unknown")),
                description=cast(str, entry.get("description", "")),
            )
        return cls(profiles, cast(str, registry.get("id_grammar", "")))

    def with_explicit_profile(self, profile: IdentityProfile) -> "ProfileSet":
        """Return a new ProfileSet additionally containing an explicitly
        supplied profile definition (e.g. a test or future profile). The
        profile identifier is metadata; nothing is coerced."""
        merged = dict(self._profiles)
        merged[profile.profile_id] = profile
        return ProfileSet(merged, self._grammar)

    @property
    def grammar(self) -> str:
        return self._grammar

    def get(self, profile_id: str) -> IdentityProfile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            classification = self.classify(profile_id)
            raise ProfileError(
                "profile",
                "profile %r is %s; known profiles: %s"
                % (profile_id, classification, sorted(self._profiles)),
            )
        return profile

    def classify(self, profile_id: str) -> str:
        """known / unknown / invalid classification (never coerced)."""
        if profile_id in self._profiles:
            return "known"
        if self._grammar and re.fullmatch(self._grammar, profile_id) is not None:
            return "unknown"
        return "invalid"

    def profile_ids(self) -> FrozenSet[str]:
        return frozenset(self._profiles)


def classify_profile_id(profile_id: str) -> str:
    """Classify a profile identifier against the default registry."""
    return ProfileSet.load_default().classify(profile_id)


def negotiate_profile(
    local_profiles: Sequence[str],
    remote_profiles: Sequence[str],
    *,
    profile_set: Optional[ProfileSet] = None,
) -> IdentityProfile:
    """Deterministically select a mutually supported, known profile.

    Selection rule (documented contract): the sorted (lexicographic)
    intersection of the two known-profile sets; the first element wins.
    Unknown or invalid identifiers are never matched — an unknown
    identifier listed by both sides is still unknown and cannot be
    negotiated into a known profile. No intersection raises
    ProfileError('negotiation', ...).
    """
    profiles = profile_set or ProfileSet.load_default()
    known_local = {p for p in local_profiles if profiles.classify(p) == "known"}
    known_remote = {p for p in remote_profiles if profiles.classify(p) == "known"}
    mutual = sorted(known_local & known_remote)
    if not mutual:
        raise ProfileError(
            "negotiation",
            "no mutually supported known profile (local=%r remote=%r)"
            % (sorted(set(local_profiles)), sorted(set(remote_profiles))),
        )
    return profiles.get(mutual[0])


@lru_cache(maxsize=1)
def _load_default_registry() -> Mapping[str, object]:
    if not PROFILE_REGISTRY_PATH.is_file():
        raise ProfileError(
            "registry", "missing identity-profile registry: %s" % PROFILE_REGISTRY_PATH
        )
    data = _load_json_no_duplicates(PROFILE_REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProfileError("registry", "identity-profile registry must be a JSON object")
    return data


def derivation_domain(derivation_rule: str) -> str:
    """Domain separation bytes declared for a derivation rule."""
    registry = cast(Dict[str, object], _load_default_registry())
    rules = cast(Mapping[str, Mapping[str, object]], registry.get("derivation_rules", {}))
    rule = rules.get(derivation_rule) if isinstance(rules, Mapping) else None
    if not isinstance(rule, Mapping) or "domain_separation" not in rule:
        raise ProfileError("derivation", "undeclared derivation rule %r" % derivation_rule)
    return str(rule["domain_separation"])


def registered_profiles() -> List[str]:
    """Sorted profile ids declared in the registry (introspection/tests)."""
    registry = cast(Dict[str, object], _load_default_registry())
    entries = registry.get("entries", {})
    if isinstance(entries, Mapping):
        return sorted(cast(Mapping[str, object], entries))
    return []
