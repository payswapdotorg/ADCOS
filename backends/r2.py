"""Cloudflare R2 evidence/artifact storage adapter (DEC-0126
bounded deployment scope, worker 2).

THE INTEGRITY CONTRACT (the design-mandated division of
authority, DEC-0126 / docs/deployment/runtime-inventory.md):
this backend holds ONLY object bytes.  Canonical metadata --
artifact references, integrity checksums, evidence records --
live in DURABLE state (the Neon-backed persistence seams behind
the accepted ADCOS authorities); :meth:`R2ArtifactStore.put`
returns the reference the durable side records, and
:meth:`R2ArtifactStore.get_verified` closes the loop by
verifying the object bytes against the durable checksum (a
divergence is the typed ``integrity-mismatch`` failure -- never
a silent substitution).

Pure standard library only (``urllib`` + ``hashlib`` +
``hmac``): NO boto3, NO requests -- AWS Signature V4 for the
S3-compatible R2 REST surface is implemented by hand
(:func:`_sign_request`, service ``s3``, region ``auto``), and
the provider surface stays behind this adapter boundary.

Transport contract (the tiny injectable seam the batteries
ride; NOTE it is the R2 shape, one member richer than the
Upstash coordination transport -- S3 object metadata such as
ETag and Content-Length lives in RESPONSE HEADERS, so the R2
transport returns them):

    Transport = Callable[[method, url, headers, body],
                          -> (status, response-headers, body)]

``response-headers`` is a plain dict with LOWERCASED header
names (the default transport normalizes; injected transports
follow the same convention).  The transport may RAISE on
network trouble (the adapter maps any transport exception to
``backend-unavailable``).  The default transport is
``urllib.request`` with a bounded timeout.

Determinism: signatures are a pure function of (method, url,
payload hash, amz_date) -- :func:`_sign_request` is fully
deterministic when ``amz_date`` is pinned (the batteries verify
byte-identical Authorization headers against an independent
re-derivation).  The production default reads the OS clock ONCE
for the ``x-amz-date`` stamp (SigV4 requires a current
timestamp); that is the sole wall-clock site in this module.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import quote, urlsplit

#: The injectable transport: (method, url, headers, body) ->
#: (status, response-headers dict, body).  May raise on network
#: failure.
Transport = Callable[
    [str, str, Dict[str, str], bytes], Tuple[int, Dict[str, str], bytes]
]

#: The frozen failure vocabulary (DEC-0126: explicit, observable,
#: backend-named failures).
REASON_CODES = (
    "missing-object",
    "backend-unavailable",
    "integrity-mismatch",
    "config-invalid",
    "protocol-error",
)

#: The bounded default REST timeout (seconds).
DEFAULT_TIMEOUT_SECONDS = 20.0

#: R2 SigV4 constants (the S3-compatible surface; region "auto").
_SERVICE = "s3"
_REGION = "auto"
_ALGORITHM = "AWS4-HMAC-SHA256"
_HOST_SUFFIX = ".r2.cloudflarestorage.com"

#: The SHA-256 of the empty payload (GET/HEAD requests sign this).
_EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()

#: Signed-header set: exactly the three AWS-mandated members.
_SIGNED_HEADERS = "host;x-amz-content-sha256;x-amz-date"

#: The S3 bucket-name shape (lowercase letters, digits, hyphens,
#: dots; 3-63 characters, alnum endpoints).
_BUCKET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")

#: The 64-hex checksum shape (an optional ``sha256:`` prefix is
#: tolerated on expected checksums).
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: The SigV4 timestamp shape (ISO 8601 basic, UTC).
_AMZ_DATE_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")

#: The object-method vocabulary this adapter signs.
_METHODS = ("GET", "HEAD", "PUT", "DELETE")


class R2ArtifactError(Exception):
    """One typed R2 artifact-storage failure (DATA).

    ``reason_code`` is drawn from the frozen :data:`REASON_CODES`
    vocabulary; ``backend`` always names the failing backend
    (``"r2"``).  ``detail`` never carries credentials or raw
    Authorization header bytes (secret hygiene).
    """

    backend = "r2"

    def __init__(self, reason_code: str, detail: str = "") -> None:
        if reason_code not in REASON_CODES:
            raise ValueError(
                "r2 artifact reason %r is not in the frozen vocabulary"
                % (reason_code,)
            )
        self.reason_code = reason_code
        self.detail = detail
        super().__init__("r2 %s: %s" % (reason_code, detail))


# ---------------------------------------------------------------------------
# The transport
# ---------------------------------------------------------------------------

def _urllib_transport(
    method: str, url: str, headers: Dict[str, str], body: bytes
) -> Tuple[int, Dict[str, str], bytes]:
    """The default transport: stdlib ``urllib`` with a bounded
    timeout.  Network failures raise (the caller maps them to
    the typed backend-unavailable error); HTTP error statuses are
    returned as (status, headers, body) triples with LOWERCASED
    header names."""
    request = urllib.request.Request(
        url, data=body if body else None, method=method
    )
    for name, value in headers.items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(
            request, timeout=DEFAULT_TIMEOUT_SECONDS
        ) as response:
            lowered = {
                str(name).lower(): value
                for name, value in response.headers.items()
            }
            return int(response.status), lowered, response.read()
    except urllib.error.HTTPError as error:
        try:
            payload = error.read()
        except Exception:  # noqa: BLE001 - best-effort error body
            payload = b""
        lowered = {
            str(name).lower(): value
            for name, value in (error.headers or {}).items()
        }
        return int(error.code), lowered, payload


def _require_nonempty_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise R2ArtifactError(
            "config-invalid", "%s must be a non-empty string" % label
        )
    return value


def _r2_endpoint(account_id: str) -> str:
    """The default R2 endpoint for one account (the documented
    S3-compatible convention)."""
    return "https://%s%s" % (account_id, _HOST_SUFFIX)


# ---------------------------------------------------------------------------
# AWS Signature V4 (hand-rolled, deterministic)
# ---------------------------------------------------------------------------

def _sign_request(
    *,
    method: str,
    endpoint: str,
    bucket: str,
    key: str,
    account_id: str,
    access_key_id: str,
    secret_access_key: str,
    payload_hash: str,
    extra_headers: Optional[Dict[str, str]] = None,
    amz_date: Optional[str] = None,
) -> Tuple[str, Dict[str, str]]:
    """Sign one R2 object request (AWS Signature V4, service
    ``s3``, region ``auto``) -- fully deterministic given
    ``(amz_date, payload)``.

    Builds the path-style object URL
    ``<endpoint>/<bucket>/<key>`` (key path segments preserved,
    each remaining character percent-encoded), derives the
    canonical request -> string-to-sign -> signing-key chain
    (``hmac``/``sha256``), and returns ``(url, headers)`` where
    ``headers`` carries ``Authorization: AWS4-HMAC-SHA256 ...``,
    ``x-amz-date`` and ``x-amz-content-sha256`` plus any
    ``extra_headers`` merged in UNSIGNED (the signed set is
    frozen: ``host;x-amz-content-sha256;x-amz-date``).

    ``amz_date`` defaults to the current UTC stamp (the sole
    wall-clock read in this module; callers pin it for
    deterministic verification).  Configuration-shape failures
    raise the typed ``config-invalid`` error.
    """
    if method not in _METHODS:
        raise R2ArtifactError(
            "config-invalid", "method %r is not an object method" % (method,)
        )
    account_id = _require_nonempty_str(account_id, "account_id")
    access_key_id = _require_nonempty_str(access_key_id, "access_key_id")
    if not isinstance(secret_access_key, str) or not secret_access_key:
        raise R2ArtifactError(
            "config-invalid", "secret_access_key must be a non-empty string"
        )
    bucket = _require_nonempty_str(bucket, "bucket")
    if not _BUCKET_PATTERN.match(bucket):
        raise R2ArtifactError(
            "config-invalid", "bucket %r is not a valid bucket name" % bucket
        )
    key = _require_nonempty_str(key, "key")
    if not isinstance(payload_hash, str) or not _SHA256_PATTERN.match(
        payload_hash
    ):
        raise R2ArtifactError(
            "config-invalid", "payload_hash must be a 64-hex sha256 digest"
        )
    if amz_date is None:
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    elif not (
        isinstance(amz_date, str) and _AMZ_DATE_PATTERN.match(amz_date)
    ):
        raise R2ArtifactError(
            "config-invalid",
            "amz_date must be the YYYYMMDDThhmmssZ UTC stamp",
        )
    if extra_headers is not None and not isinstance(extra_headers, dict):
        raise R2ArtifactError(
            "config-invalid", "extra_headers must be a header mapping"
        )
    parts = urlsplit(endpoint) if isinstance(endpoint, str) else None
    if parts is None or parts.scheme != "https" or not parts.netloc:
        raise R2ArtifactError(
            "config-invalid", "endpoint must be an absolute https URL"
        )
    host = parts.netloc.lower()
    if host != "%s%s" % (account_id, _HOST_SUFFIX):
        raise R2ArtifactError(
            "config-invalid",
            "endpoint host %r does not match the account's R2 endpoint "
            "https://%s%s" % (host, account_id, _HOST_SUFFIX),
        )

    canonical_uri = "/%s/%s" % (quote(bucket, safe=""), quote(key, safe="/"))
    canonical_querystring = ""
    canonical_headers = (
        "host:%s\nx-amz-content-sha256:%s\nx-amz-date:%s\n"
        % (host, payload_hash, amz_date)
    )
    canonical_request = "\n".join(
        [
            method,
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            _SIGNED_HEADERS,
            payload_hash,
        ]
    )
    datestamp = amz_date[:8]
    credential_scope = "%s/%s/%s/aws4_request" % (
        datestamp,
        _REGION,
        _SERVICE,
    )
    string_to_sign = "\n".join(
        [
            _ALGORITHM,
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    def _hmac(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    key_date = _hmac(("AWS4" + secret_access_key).encode("utf-8"), datestamp)
    key_region = _hmac(key_date, _REGION)
    key_service = _hmac(key_region, _SERVICE)
    key_signing = _hmac(key_service, "aws4_request")
    signature = hmac.new(
        key_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    authorization = "%s Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (
        _ALGORITHM,
        access_key_id,
        credential_scope,
        _SIGNED_HEADERS,
        signature,
    )

    url = "%s://%s%s" % (parts.scheme, host, canonical_uri)
    headers: Dict[str, str] = {
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
        "Authorization": authorization,
    }
    if extra_headers:
        for name, value in extra_headers.items():
            headers[str(name)] = str(value)
    return url, headers


# ---------------------------------------------------------------------------
# The artifact store
# ---------------------------------------------------------------------------

class R2ArtifactStore:
    """The Cloudflare R2 object store for ADCOS artifacts and
    evidence bytes (put / get / head / delete / verified read).

    The ArtifactRef (what :meth:`put` returns and the DURABLE
    side records -- R2 itself holds only the bytes):

    ``{"key": ..., "size": <bytes>, "content_sha256": <hex>,
    "etag": <from response>, "backend": "r2"}``

    :meth:`delete` returns the deletion reference
    ``{"key": ..., "deleted": True, "backend": "r2"}`` (S3
    idempotent semantics: the deletion is observable through
    the follow-up read, which is the typed ``missing-object``
    failure).

    Failure posture (DEC-0126: explicit, observable, never a
    silent degradation): a missing object is the typed
    ``missing-object`` error; a checksum divergence in
    :meth:`get_verified` is the typed ``integrity-mismatch``
    error; backend trouble is the typed ``backend-unavailable``
    error (transport exceptions included); credential trouble is
    ``config-invalid``; a malformed successful response is
    ``protocol-error``.
    """

    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        transport: Optional[Transport] = None,
    ) -> None:
        account_id = _require_nonempty_str(account_id, "account_id")
        access_key_id = _require_nonempty_str(access_key_id, "access_key_id")
        if not isinstance(secret_access_key, str) or not secret_access_key:
            raise R2ArtifactError(
                "config-invalid",
                "secret_access_key must be a non-empty string",
            )
        bucket = _require_nonempty_str(bucket, "bucket")
        if not _BUCKET_PATTERN.match(bucket):
            raise R2ArtifactError(
                "config-invalid",
                "bucket %r is not a valid bucket name" % bucket,
            )
        self._account_id = account_id
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._bucket = bucket
        self._endpoint = _r2_endpoint(account_id)
        self._transport = (
            transport if transport is not None else _urllib_transport
        )

    @property
    def bucket(self) -> str:
        """The artifact bucket (public: references carry it)."""
        return self._bucket

    def _send(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        ok_statuses: Tuple[int, ...] = (200,),
    ) -> Tuple[int, Dict[str, str], bytes]:
        """One signed transport call with the frozen status
        mapping (``ok_statuses`` widens the success set for the
        S3 no-content success -- DELETE answers 204).  Details
        never carry credentials or raw header bytes."""
        try:
            status, response_headers, response_body = self._transport(
                method, url, headers, body
            )
        except Exception as error:  # noqa: BLE001 - fail closed, typed
            raise R2ArtifactError(
                "backend-unavailable",
                "object %s: transport raised %s"
                % (method, type(error).__name__),
            ) from error
        if status in ok_statuses:
            return status, response_headers, response_body
        if status == 404:
            raise R2ArtifactError(
                "missing-object",
                "object request %s returned HTTP 404" % method,
            )
        if status in (401, 403):
            raise R2ArtifactError(
                "config-invalid",
                "object request %s rejected with HTTP %d (credentials "
                "refused)" % (method, status),
            )
        raise R2ArtifactError(
            "backend-unavailable",
            "object request %s returned HTTP %d" % (method, status),
        )

    def _object_url_and_headers(
        self,
        *,
        method: str,
        key: str,
        payload_hash: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, Dict[str, str]]:
        return _sign_request(
            method=method,
            endpoint=self._endpoint,
            bucket=self._bucket,
            key=key,
            account_id=self._account_id,
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
            payload_hash=payload_hash,
            extra_headers=extra_headers,
        )

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """Store one artifact; return its ArtifactRef (the
        reference the DURABLE side records -- see the class
        docstring).  The object bytes are signed with their
        SHA-256 (``x-amz-content-sha256``); the ETag is taken
        from the response (S3 returns the double-quoted digest;
        the reference carries it unquoted)."""
        key = _require_nonempty_str(key, "key")
        if not isinstance(data, (bytes, bytearray)):
            raise R2ArtifactError(
                "config-invalid", "data must be bytes"
            )
        payload = bytes(data)
        content_type = _require_nonempty_str(
            content_type, "content_type"
        )
        payload_hash = hashlib.sha256(payload).hexdigest()
        url, headers = self._object_url_and_headers(
            method="PUT",
            key=key,
            payload_hash=payload_hash,
            extra_headers={"Content-Type": content_type},
        )
        status, response_headers, _body = self._send(
            "PUT", url, headers, payload
        )
        etag = response_headers.get("etag")
        if not etag:
            raise R2ArtifactError(
                "protocol-error",
                "PUT succeeded without an ETag response header",
            )
        return {
            "key": key,
            "size": len(payload),
            "content_sha256": payload_hash,
            "etag": etag.strip('"'),
            "backend": "r2",
        }

    def delete(self, key: str) -> dict:
        """Delete one artifact's object bytes and return the
        deletion reference
        ``{"key": ..., "deleted": True, "backend": "r2"}``.

        S3-compatible idempotent semantics: R2 answers 204 (or
        200) whether or not the key existed -- existence is
        never inferred here; the deletion is OBSERVABLE through
        the follow-up read, which is the typed
        ``missing-object`` failure.  Backend trouble is the
        typed ``backend-unavailable`` error (a deletion is
        never silent in either direction)."""
        key = _require_nonempty_str(key, "key")
        url, headers = self._object_url_and_headers(
            method="DELETE", key=key, payload_hash=_EMPTY_PAYLOAD_SHA256
        )
        self._send("DELETE", url, headers, b"", ok_statuses=(200, 204))
        return {"key": key, "deleted": True, "backend": "r2"}

    def get(self, key: str) -> bytes:
        """Fetch one artifact's bytes (byte-exact round trip);
        a missing object is the typed ``missing-object``
        error."""
        key = _require_nonempty_str(key, "key")
        url, headers = self._object_url_and_headers(
            method="GET", key=key, payload_hash=_EMPTY_PAYLOAD_SHA256
        )
        _status, _response_headers, body = self._send("GET", url, headers, b"")
        return body

    def head(self, key: str) -> dict:
        """Read one artifact's object metadata (no bytes): the
        reference-shaped ``{"key": ..., "size": ..., "etag":
        ...}``; a missing object is the typed ``missing-object``
        error."""
        key = _require_nonempty_str(key, "key")
        url, headers = self._object_url_and_headers(
            method="HEAD", key=key, payload_hash=_EMPTY_PAYLOAD_SHA256
        )
        _status, response_headers, _body = self._send(
            "HEAD", url, headers, b""
        )
        length = response_headers.get("content-length")
        if length is None or not str(length).strip().isdigit():
            raise R2ArtifactError(
                "protocol-error",
                "HEAD succeeded without a Content-Length header",
            )
        etag = response_headers.get("etag")
        if not etag:
            raise R2ArtifactError(
                "protocol-error",
                "HEAD succeeded without an ETag response header",
            )
        return {
            "key": key,
            "size": int(str(length).strip()),
            "etag": etag.strip('"'),
        }

    def get_verified(self, key: str, content_sha256: str) -> bytes:
        """Fetch one artifact's bytes AND verify them against
        the DURABLE-side checksum (the integrity contract: R2
        holds only object bytes; the canonical checksum lives in
        durable state; this method closes the loop).

        A divergence is the typed ``integrity-mismatch`` error
        -- never a silent substitution.  The expected checksum
        may carry an optional ``sha256:`` prefix (the evidence
        record convention) and must otherwise be 64 hex
        characters (malformed expectations fail closed as
        ``config-invalid``)."""
        key = _require_nonempty_str(key, "key")
        if not isinstance(content_sha256, str) or not content_sha256.strip():
            raise R2ArtifactError(
                "config-invalid",
                "content_sha256 must be a non-empty checksum string",
            )
        expected = content_sha256.strip().lower()
        if expected.startswith("sha256:"):
            expected = expected[len("sha256:"):]
        if not _SHA256_PATTERN.match(expected):
            raise R2ArtifactError(
                "config-invalid",
                "content_sha256 must be a 64-hex sha256 digest",
            )
        data = self.get(key)
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected:
            raise R2ArtifactError(
                "integrity-mismatch",
                "object %r diverges from the durable checksum "
                "(stored %s, expected %s)" % (key, digest, expected),
            )
        return data
