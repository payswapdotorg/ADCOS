"""Revocation metadata (WORK-004 section 10).

Revocation is an explicit administrative act with metadata,
distinguishable from time-based expiry. This module represents local
revocation state only — distribution, federation trust policy,
reputation, and authorization are out of scope (later Work Items).
Revocation metadata is non-secret and serializable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RevocationInfo:
    """Why and when a credential was revoked. Non-secret metadata."""

    revoked_at: str  # RFC 3339 UTC
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.revoked_at, str) or not self.revoked_at:
            raise ValueError("revoked_at must be a non-empty RFC 3339 UTC string")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("revocation reason must be a non-empty string")
        if len(self.reason) > 256:
            raise ValueError("revocation reason too long (max 256 characters)")

    def to_dict(self) -> dict:
        return {"reason": self.reason, "revoked_at": self.revoked_at}

    @classmethod
    def from_dict(cls, data: object) -> "RevocationInfo":
        if not isinstance(data, dict):
            raise ValueError("revocation info must be an object")
        revoked_at = data.get("revoked_at")
        reason = data.get("reason")
        if not isinstance(revoked_at, str) or not isinstance(reason, str):
            raise ValueError("revocation info requires string revoked_at and reason")
        return cls(revoked_at=revoked_at, reason=reason)

    def __repr__(self) -> str:
        return "RevocationInfo(revoked_at=%r, reason=%r)" % (self.revoked_at, self.reason)
