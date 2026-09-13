#!/usr/bin/env python3
"""T5 Cloudflare R2 evidence/artifact storage battery (DEC-0126
bounded deployment scope, worker 2; deterministic, stdlib only,
NO network).

End-to-end verification of ``backends/r2.py`` -- the R2
artifact-storage adapter -- against a deterministic in-memory
fake of the minimal S3-compatible REST surface (a dict object
store; ETag/Content-Length served from LOWERCASED response
headers per the documented 3-tuple transport contract):

Verified surface (each criterion mapped to its cases):

- **module surface** (case 01): pure stdlib only (the r2 adapter
  composes NO in-repo seams -- it is pure infrastructure), the
  metadata-boundary invariants documented in the module
  docstring (R2 holds ONLY object bytes; canonical metadata
  lives in DURABLE state; a divergence is never a silent
  substitution), and the frozen typed-error vocabulary;
- **configuration** (case 02): bad account id / access key id /
  secret access key / bucket shapes fail closed as
  ``config-invalid``, and so do malformed ``put`` /
  ``get_verified`` arguments;
- **put** (case 03): stores the exact object bytes and returns
  the ArtifactRef the durable side records -- key + checksum +
  size + the response ETag (pass-through, unquoted) + backend;
- **get** (case 04): byte-identical round trips (empty, binary
  and multi-KiB payloads; overwrite is last-write-wins);
- **get_verified** (case 05): the success path when the recorded
  checksum matches (``sha256:`` prefix and uppercase hex
  tolerated);
- **checksum discipline** (case 06): the recorded checksum
  equals the INDEPENDENTLY computed sha256 of the bytes AND the
  SigV4-signed wire payload hash; the ETag is the response's own
  digest, never adapter-computed;
- **missing object** (case 07): the typed ``missing-object``
  failure on get/head/get_verified (the HTTP 404 mapping
  included) -- never a silent empty read;
- **integrity mismatch** (case 08): corrupted stored bytes or a
  divergent durable expectation raise the typed
  ``integrity-mismatch`` failure -- never a silent substitution;
- **delete + get-after-delete** (case 09): delete returns the
  deletion reference; every follow-up read is the typed
  ``missing-object``; re-deleting is idempotent (S3 semantics);
- **backend failure** (case 10): a dead transport and HTTP
  400/409/429/5xx raise the typed ``backend-unavailable`` error
  (401/403 are the frozen ``config-invalid`` credential-refusal
  mapping -- still typed, still fail-closed); no silent success;
- **protocol errors** (case 11): successful responses that lack
  the S3 response headers (ETag, Content-Length) or carry a
  non-numeric length raise the typed ``protocol-error``;
- **SigV4 signing** (case 12): the Authorization header format
  (AWS4-HMAC-SHA256 Credential=<access>/<date>/auto/s3/
  aws4_request, the frozen SignedHeaders host;x-amz-content-
  sha256;x-amz-date, a 64-hex signature), byte-identity against
  an INDEPENDENT re-derivation of the whole SigV4 chain, and
  stability (identical inputs -> identical signature; the
  signature binds method/key/payload/date);
- **secret hygiene** (case 13): the access key id and the secret
  access key NEVER appear in any error surface (the
  Authorization wire header is their sole carrier, by SigV4
  design);
- **determinism** (case 14): identical traces produce identical
  references, command logs and typed-failure reasons across
  fresh worlds; the battery's deterministic key allocator
  (content digest + sequence -- the DURABLE side owns key
  allocation) yields a unique key per put;
- **the metadata-boundary contract** (case 15): ``put`` returns
  ONLY a reference (exactly key/size/content_sha256/etag/
  backend -- no state authority beyond it); the fake's stored
  object is exactly the payload bytes (R2 holds only object
  data; canonical metadata belongs to durable state).

Every case runs OFFLINE against the injectable fake transport.
Apart from case 12 (which calls the module-documented
``_sign_request`` seam directly with a PINNED ``amz_date`` --
the sole wall-clock read in the adapter is that stamp, and the
module docstring designates it for exactly this battery
verification), the battery exercises the PUBLIC adapter surface
only, and every PASS is manufactured against independently
recomputed expectations (digests, signatures, references) --
never against the adapter's own outputs reflected back.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import re
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple
from urllib.parse import quote, unquote

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import backends.r2 as r2_module  # noqa: E402
from backends.r2 import (  # noqa: E402
    REASON_CODES,
    R2ArtifactError,
    R2ArtifactStore,
)

Result = Tuple[str, bool, str]

_ACCOUNT_ID = "battery-account-id-0001"
_ACCESS_KEY_ID = "battery-access-key-id-0001"
_SECRET_ACCESS_KEY = "battery-secret-access-key-material-0001"
_BUCKET = "adcos-artifacts-battery"
_HOST = "%s.r2.cloudflarestorage.com" % _ACCOUNT_ID
_ENDPOINT = "https://%s" % _HOST
_URL_PREFIX = "%s/%s/" % (_ENDPOINT, _BUCKET)
_MODULE = REPO_ROOT / "backends" / "r2.py"

_AMZ_DATE = "20260913T000000Z"

_AUTH_PATTERN = re.compile(
    r"^AWS4-HMAC-SHA256 "
    r"Credential=(?P<access>[^/]+)/(?P<date>[0-9]{8})/auto/s3/aws4_request, "
    r"SignedHeaders=host;x-amz-content-sha256;x-amz-date, "
    r"Signature=(?P<signature>[0-9a-f]{64})$"
)
_AMZ_DATE_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")
_HEX64_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _auto_key(payload: bytes, sequence: int) -> str:
    """The battery's deterministic key allocator -- standing in
    for the DURABLE side, which owns key allocation (the adapter
    takes none: ``put`` REQUIRES an explicit key, pinned in the
    metadata-boundary case).  Content digest + sequence position:
    unique per put, stable per construction position."""
    return "artifacts/2026-09-13/%s/%03d" % (
        _sha256_hex(payload)[:12],
        sequence,
    )


# ---------------------------------------------------------------------------
# The deterministic world (fake S3-compatible REST transport)
# ---------------------------------------------------------------------------

class FakeR2Transport:
    """The minimal R2/S3 object surface, in memory.

    A dict object store (key -> [bytes, content-type]) speaking
    the documented 3-tuple transport contract:
    ``(method, url, headers, body) -> (status, response-headers
    with LOWERCASED names, body)``.  Every request's SigV4
    Authorization header is VALIDATED (format, credential scope,
    the frozen SignedHeaders set, the 64-hex signature, the
    x-amz-content-sha256 == sha256(body) binding, the x-amz-date
    shape, the path-style URL) with any violation recorded in
    ``violations`` -- the audit log the signing case pins.
    ``calls``/``signed_payload_hashes`` record the deterministic
    (method, key[, payload-hash]) audit logs the determinism case
    pins; one-shot failure scripting: ``raise_error`` (transport
    exception), ``next_status`` (+ ``next_headers``) for raw HTTP
    statuses and header-malformed 200s.  ETags are the fake's own
    MD5 digests (double-quoted, as S3 serves them) -- a DIFFERENT
    hash family than the adapter's sha256 checksums, so a
    pass-through ETag is distinguishable from an adapter-computed
    one.  Nothing derived from the wall clock is ever recorded.
    """

    def __init__(self) -> None:
        self.objects: dict = {}  # key -> [bytes, content-type]
        self.calls: List[Tuple[str, str]] = []
        self.signed_payload_hashes: List[Tuple[str, str, str]] = []
        self.violations: List[str] = []
        self.raise_error: Optional[BaseException] = None
        self.next_status: Optional[int] = None
        self.next_headers: Optional[dict] = None

    # -- helpers -------------------------------------------------------

    def stored_bytes(self, key: str) -> Optional[bytes]:
        entry = self.objects.get(key)
        return None if entry is None else entry[0]

    def stored_content_type(self, key: str) -> Optional[str]:
        entry = self.objects.get(key)
        return None if entry is None else entry[1]

    def corrupt(self, key: str, data: bytes) -> None:
        """A foreign writer's tampering -- the battery fixture
        for the integrity-mismatch case."""
        if key in self.objects:
            self.objects[key][0] = bytes(data)

    # -- the transport -------------------------------------------------

    def __call__(
        self, method: str, url: str, headers: dict, body: bytes
    ) -> Tuple[int, dict, bytes]:
        lowered = {
            str(name).lower(): value for name, value in headers.items()
        }
        self._validate_request(method, url, lowered, body)
        key = unquote(url[len(_URL_PREFIX):])
        self.calls.append((method, key))
        self.signed_payload_hashes.append(
            (method, key, lowered.get("x-amz-content-sha256", ""))
        )
        if self.raise_error is not None:
            error, self.raise_error = self.raise_error, None
            raise error
        if self.next_status is not None:
            status = self.next_status
            self.next_status = None
            response_headers = self.next_headers
            self.next_headers = None
            return status, (response_headers or {}), b""
        if method == "PUT":
            payload = bytes(body)
            self.objects[key] = [
                payload,
                lowered.get("content-type", "application/octet-stream"),
            ]
            return (
                200,
                {
                    "etag": '"%s"' % hashlib.md5(payload).hexdigest(),
                    "content-length": "0",
                },
                b"",
            )
        if method in ("GET", "HEAD"):
            entry = self.objects.get(key)
            if entry is None:
                return 404, {}, b""
            data = entry[0]
            response_headers = {
                "etag": '"%s"' % hashlib.md5(data).hexdigest(),
                "content-length": str(len(data)),
            }
            return 200, response_headers, (data if method == "GET" else b"")
        if method == "DELETE":
            self.objects.pop(key, None)
            return 204, {}, b""
        self.violations.append("unexpected method %r" % (method,))
        return 400, {}, b""

    def _validate_request(
        self, method: str, url: str, headers: dict, body: bytes
    ) -> None:
        if method not in ("GET", "HEAD", "PUT", "DELETE"):
            self.violations.append("non-object method %r" % (method,))
        if not url.startswith(_URL_PREFIX):
            self.violations.append("url is not the path-style object url")
        auth = headers.get("authorization", "")
        match = _AUTH_PATTERN.match(auth)
        if match is None:
            self.violations.append("malformed Authorization header")
        else:
            if match.group("access") != _ACCESS_KEY_ID:
                self.violations.append(
                    "Authorization carries the wrong access key id"
                )
            if match.group("date") != headers.get("x-amz-date", "")[:8]:
                self.violations.append(
                    "the Credential date and x-amz-date disagree"
                )
        amz_date = headers.get("x-amz-date", "")
        if not _AMZ_DATE_PATTERN.match(amz_date):
            self.violations.append("malformed x-amz-date stamp")
        payload_hash = headers.get("x-amz-content-sha256", "")
        if payload_hash != _sha256_hex(bytes(body)):
            self.violations.append(
                "x-amz-content-sha256 is not the sha256 of the request body"
            )
        if method == "PUT" and not str(
            headers.get("content-type", "")
        ).strip():
            self.violations.append("PUT without a Content-Type header")


def _world() -> FakeR2Transport:
    return FakeR2Transport()


def _store(
    fake: FakeR2Transport,
    *,
    account_id: str = _ACCOUNT_ID,
    access_key_id: str = _ACCESS_KEY_ID,
    secret_access_key: str = _SECRET_ACCESS_KEY,
    bucket: str = _BUCKET,
) -> R2ArtifactStore:
    return R2ArtifactStore(
        account_id=account_id,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        bucket=bucket,
        transport=fake,
    )


def _expect_artifact_error(
    name: str,
    operation,
    reason: str,
    problems: List[str],
    *,
    secrets: Tuple[str, ...] = (),
) -> None:
    """Run ``operation`` and require the typed artifact error with
    exactly ``reason`` (never a silent success); scan the error
    surface for leaked secrets."""
    try:
        operation()
    except R2ArtifactError as error:
        if error.reason_code != reason:
            problems.append(
                "%s: reason %r (want %r)" % (name, error.reason_code, reason)
            )
        if error.backend != "r2":
            problems.append("%s: backend %r" % (name, error.backend))
        rendered = "%s|%s|%r" % (str(error), error.detail, error)
        for secret in secrets:
            if secret and secret in rendered:
                problems.append("%s: secret leaked into the error surface" % name)
    except Exception as error:  # noqa: BLE001 - wrong failure kind
        problems.append(
            "%s: raised %r instead of the typed artifact error"
            % (name, error)
        )
    else:
        problems.append("%s: no error raised (silent success)" % name)


# ---------------------------------------------------------------------------
# An independent SigV4 re-derivation (the battery's own, built from
# the AWS Signature V4 construction -- never from the adapter)
# ---------------------------------------------------------------------------

def _independent_authorization(
    *,
    method: str,
    host: str,
    canonical_uri: str,
    payload_hash: str,
    amz_date: str,
    access_key_id: str,
    secret_access_key: str,
) -> str:
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_headers = (
        "host:%s\nx-amz-content-sha256:%s\nx-amz-date:%s\n"
        % (host, payload_hash, amz_date)
    )
    canonical_request = "\n".join(
        [
            method,
            canonical_uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    datestamp = amz_date[:8]
    credential_scope = "%s/auto/s3/aws4_request" % datestamp
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            _sha256_hex(canonical_request.encode("utf-8")),
        ]
    )

    def _hmac(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    key = _hmac(("AWS4" + secret_access_key).encode("utf-8"), datestamp)
    key = _hmac(key, "auto")
    key = _hmac(key, "s3")
    key = _hmac(key, "aws4_request")
    signature = hmac.new(
        key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return (
        "AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s"
        % (access_key_id, credential_scope, signed_headers, signature)
    )


def _signature_of(authorization: str) -> str:
    match = _AUTH_PATTERN.match(authorization)
    return "" if match is None else match.group("signature")


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def case_01_module_surface(results: List[Result]) -> None:
    """Pure stdlib only (no in-repo seams, no third party); the
    metadata-boundary invariants documented; the frozen
    typed-error vocabulary."""
    problems: List[str] = []
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    third_party = sorted(
        name
        for name in imported
        if name not in sys.stdlib_module_names
    )
    if third_party:
        problems.append("third-party imports: %s" % (third_party,))
    docstring = ast.get_docstring(tree) or ""
    for phrase in (
        "ONLY object bytes",
        "Canonical metadata",
        "DURABLE state",
        "silent substitution",
        "integrity-mismatch",
    ):
        if phrase not in docstring:
            problems.append(
                "the invariant phrase %r is not documented" % (phrase,)
            )
    if REASON_CODES != (
        "missing-object",
        "backend-unavailable",
        "integrity-mismatch",
        "config-invalid",
        "protocol-error",
    ):
        problems.append("the reason vocabulary drifted: %r" % (REASON_CODES,))
    try:
        R2ArtifactError("not-a-reason")
    except ValueError:
        pass
    except Exception as error:  # noqa: BLE001
        problems.append("unknown reason accepted: %r" % (error,))
    else:
        problems.append("unknown reason accepted silently")
    probe = R2ArtifactError("missing-object", "probe")
    if (
        probe.backend != "r2"
        or probe.reason_code != "missing-object"
        or probe.detail != "probe"
        or str(probe) != "r2 missing-object: probe"
    ):
        problems.append("the typed error carries the wrong surface data")
    if problems:
        results.append(fail("01 module surface", "; ".join(problems)))
    else:
        results.append(
            ok(
                "01 module surface",
                "stdlib only (no seams composed); the R2-holds-only-object-"
                "bytes / canonical-metadata-in-durable-state invariants "
                "documented; 5-member frozen vocabulary",
            )
        )


def case_02_config_invalid(results: List[Result]) -> None:
    """Constructor-shape failures (account id / access key id /
    secret access key / bucket) and malformed put/get_verified
    arguments all fail closed as config-invalid."""
    problems: List[str] = []
    fake = _world()
    for bad_account in ("", "   ", None, 7):
        _expect_artifact_error(
            "account_id=%r" % (bad_account,),
            lambda bad=bad_account: _store(fake, account_id=bad),
            "config-invalid",
            problems,
        )
    for bad_access in ("", "   ", None):
        _expect_artifact_error(
            "access_key_id=%r" % (bad_access,),
            lambda bad=bad_access: _store(fake, access_key_id=bad),
            "config-invalid",
            problems,
        )
    for bad_secret in ("", None, 7):
        _expect_artifact_error(
            "secret_access_key=%r" % (bad_secret,),
            lambda bad=bad_secret: _store(fake, secret_access_key=bad),
            "config-invalid",
            problems,
        )
    for bad_bucket in (
        "",
        "AB",
        "ab",
        "-abc",
        "abc-",
        "under_score",
        "has space",
        "a" * 64,
    ):
        _expect_artifact_error(
            "bucket=%r" % (bad_bucket,),
            lambda bad=bad_bucket: _store(fake, bucket=bad),
            "config-invalid",
            problems,
        )
    store = _store(fake)
    _expect_artifact_error(
        "empty put key",
        lambda: store.put("", b"data"),
        "config-invalid",
        problems,
    )
    _expect_artifact_error(
        "whitespace put key",
        lambda: store.put("   ", b"data"),
        "config-invalid",
        problems,
    )
    for bad_data in ("not-bytes", None, 7, ["list"]):
        _expect_artifact_error(
            "put data=%r" % (type(bad_data).__name__,),
            lambda bad=bad_data: store.put("artifacts/x", bad_data),
            "config-invalid",
            problems,
        )
    _expect_artifact_error(
        "empty content_type",
        lambda: store.put("artifacts/x", b"data", content_type=""),
        "config-invalid",
        problems,
    )
    _expect_artifact_error(
        "empty get key",
        lambda: store.get(""),
        "config-invalid",
        problems,
    )
    for bad_checksum in (
        "",
        "   ",
        None,
        7,
        "not-a-checksum",
        "z" * 64,
        "0" * 63,
        "0" * 65,
        "sha256:" + "z" * 64,
    ):
        _expect_artifact_error(
            "get_verified checksum=%r" % (type(bad_checksum).__name__,),
            lambda bad=bad_checksum: store.get_verified(
                "artifacts/x", bad_checksum
            ),
            "config-invalid",
            problems,
        )
    if problems:
        results.append(fail("02 config-invalid shapes", "; ".join(problems)))
    else:
        results.append(
            ok(
                "02 config-invalid shapes",
                "bad account/access/secret/bucket and malformed put/"
                "get_verified arguments all fail closed as config-invalid",
            )
        )


def case_03_put_reference(results: List[Result]) -> None:
    """put stores the exact bytes and returns the ArtifactRef the
    durable side records (key + checksum + size + the response
    ETag pass-through + backend); head agrees with it."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    payload = b"adcos artifact evidence payload \x00\x01\x02"
    key = "artifacts/2026-09-13/evidence-observation-001.bin"
    reference = store.put(key, payload, content_type="application/json")
    if fake.stored_bytes(key) != payload:
        problems.append("the stored object is not the exact payload bytes")
    if fake.stored_content_type(key) != "application/json":
        problems.append("the declared content type did not reach the object")
    if sorted(reference) != [
        "backend",
        "content_sha256",
        "etag",
        "key",
        "size",
    ]:
        problems.append(
            "the ArtifactRef members drifted: %s" % (sorted(reference),)
        )
    if reference["key"] != key or reference["size"] != len(payload):
        problems.append("the reference key/size drifted")
    if reference["backend"] != "r2":
        problems.append("the reference backend drifted")
    if reference["content_sha256"] != _sha256_hex(payload):
        problems.append("the reference checksum is not the payload sha256")
    if reference["etag"] != hashlib.md5(payload).hexdigest():
        problems.append(
            "the reference ETag is not the response's own digest "
            "(pass-through with the S3 quotes stripped)"
        )
    headed = store.head(key)
    if sorted(headed) != ["etag", "key", "size"]:
        problems.append("the head reference members drifted")
    if (
        headed["key"] != key
        or headed["size"] != len(payload)
        or headed["etag"] != reference["etag"]
    ):
        problems.append("head disagrees with the put reference")
    default_type = store.put("artifacts/2026-09-13/default-type", b"{}")
    if (
        default_type["content_sha256"] != _sha256_hex(b"{}")
        or fake.stored_content_type("artifacts/2026-09-13/default-type")
        != "application/octet-stream"
    ):
        problems.append("the default content type discipline drifted")
    if fake.violations:
        problems.append("wire violations: %r" % (fake.violations,))
    if problems:
        results.append(fail("03 put reference", "; ".join(problems)))
    else:
        results.append(
            ok(
                "03 put reference",
                "stores the exact bytes; returns the 5-member ArtifactRef "
                "(key/checksum/size/etag/backend, the ETag a pass-through); "
                "head agrees",
            )
        )


def case_04_get_round_trip(results: List[Result]) -> None:
    """get round-trips byte-identical content (empty, binary,
    unicode and multi-KiB payloads; overwrite is last-write-wins)."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    payloads = (
        b"",
        b"adcos",
        b"\x00\xff\x00 binary \n\r bytes \x7f",
        "unicode-\u00e9vidence-\u2713".encode("utf-8"),
        b"x" * 4096,
        bytes(range(256)),
    )
    for sequence, payload in enumerate(payloads):
        key = _auto_key(payload, sequence)
        store.put(key, payload)
        fetched = store.get(key)
        if not isinstance(fetched, bytes):
            problems.append("get did not return raw bytes")
        if fetched != payload:
            problems.append(
                "round trip %d diverged (%d vs %d bytes)"
                % (sequence, len(fetched), len(payload))
            )
    first = b"first-write evidence"
    second = b"second-write evidence"
    overwrite_key = "artifacts/2026-09-13/overwrite.bin"
    store.put(overwrite_key, first)
    reference = store.put(overwrite_key, second)
    if store.get(overwrite_key) != second:
        problems.append("overwrite did not become last-write-wins")
    if reference["content_sha256"] != _sha256_hex(second):
        problems.append("the overwrite reference kept the stale checksum")
    if fake.violations:
        problems.append("wire violations: %r" % (fake.violations,))
    if problems:
        results.append(fail("04 get round trip", "; ".join(problems)))
    else:
        results.append(
            ok(
                "04 get round trip",
                "byte-identical round trips for %d payloads (empty, binary, "
                "unicode, multi-KiB); overwrite is last-write-wins"
                % len(payloads),
            )
        )


def case_05_get_verified_success(results: List[Result]) -> None:
    """get_verified returns the bytes when the recorded checksum
    matches (the sha256: prefix and uppercase hex tolerated)."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    payload = b"verified evidence payload"
    key = "artifacts/2026-09-13/verified.bin"
    reference = store.put(key, payload)
    checksum = reference["content_sha256"]
    fetched = store.get_verified(key, checksum)
    if fetched != payload:
        problems.append("the verified read did not return the exact bytes")
    prefixed = store.get_verified(key, "sha256:" + checksum)
    if prefixed != payload:
        problems.append("the sha256:-prefixed expectation was rejected")
    upper = store.get_verified(key, checksum.upper())
    if upper != payload:
        problems.append("the uppercase-hex expectation was rejected")
    padded = store.get_verified(key, "  %s  " % checksum)
    if padded != payload:
        problems.append("the whitespace-padded expectation was rejected")
    if fake.violations:
        problems.append("wire violations: %r" % (fake.violations,))
    if problems:
        results.append(fail("05 get_verified success", "; ".join(problems)))
    else:
        results.append(
            ok(
                "05 get_verified success",
                "verified reads return the exact bytes for the recorded "
                "checksum (sha256: prefix, uppercase hex and padding "
                "tolerated)",
            )
        )


def case_06_checksum_discipline(results: List[Result]) -> None:
    """The recorded checksum equals the INDEPENDENTLY computed
    sha256 of the bytes and the SigV4-signed wire payload hash;
    the ETag is the response's own digest, never adapter-computed."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    payload = b"checksum discipline payload \x00\x01"
    key = "artifacts/2026-09-13/checksum.bin"
    reference = store.put(key, payload)
    if reference["content_sha256"] != _sha256_hex(payload):
        problems.append("the recorded checksum is not the independent sha256")
    if not _HEX64_PATTERN.match(reference["content_sha256"]):
        problems.append("the recorded checksum is not 64 lowercase hex")
    wire_put = [
        entry
        for entry in fake.signed_payload_hashes
        if entry[0] == "PUT" and entry[1] == key
    ]
    if len(wire_put) != 1 or wire_put[0][2] != _sha256_hex(payload):
        problems.append(
            "the signed wire payload hash is not the payload sha256"
        )
    if reference["etag"] == reference["content_sha256"]:
        problems.append(
            "the ETag collides with the checksum -- the fake serves MD5 "
            "ETags, so a collision means the adapter computed the ETag"
        )
    fetched = store.get(key)
    if _sha256_hex(fetched) != reference["content_sha256"]:
        problems.append("the fetched bytes do not hash to the recorded checksum")
    if fake.violations:
        problems.append("wire violations: %r" % (fake.violations,))
    if problems:
        results.append(fail("06 checksum discipline", "; ".join(problems)))
    else:
        results.append(
            ok(
                "06 checksum discipline",
                "recorded checksum == independent sha256 == the signed wire "
                "payload hash; the ETag is the response's own (MD5) digest",
            )
        )


def case_07_missing_object(results: List[Result]) -> None:
    """get/head/get_verified on a missing object raise the typed
    missing-object failure (the HTTP 404 mapping included) --
    never a silent empty read."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    absent = "artifacts/2026-09-13/never-put.bin"
    _expect_artifact_error(
        "get missing",
        lambda: store.get(absent),
        "missing-object",
        problems,
    )
    _expect_artifact_error(
        "head missing",
        lambda: store.head(absent),
        "missing-object",
        problems,
    )
    _expect_artifact_error(
        "get_verified missing",
        lambda: store.get_verified(absent, "0" * 64),
        "missing-object",
        problems,
    )
    # the 404 STATUS mapping (not fake absence): a stored object
    # whose response is scripted as 404 is still missing-object.
    present = "artifacts/2026-09-13/present.bin"
    store.put(present, b"present bytes")
    fake.next_status = 404
    _expect_artifact_error(
        "get scripted-404",
        lambda: store.get(present),
        "missing-object",
        problems,
    )
    fake.next_status = 404
    _expect_artifact_error(
        "head scripted-404",
        lambda: store.head(present),
        "missing-object",
        problems,
    )
    if problems:
        results.append(fail("07 missing object", "; ".join(problems)))
    else:
        results.append(
            ok(
                "07 missing object",
                "get/head/get_verified on a missing key raise the typed "
                "missing-object (the 404 mapping pinned); never a silent "
                "empty read",
            )
        )


def case_08_integrity_mismatch(results: List[Result]) -> None:
    """A corrupted object or a divergent durable expectation
    raises the typed integrity-mismatch failure -- never a silent
    substitution."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    original = b"original evidence bytes"
    key = "artifacts/2026-09-13/integrity.bin"
    reference = store.put(key, original)
    recorded = reference["content_sha256"]
    fake.corrupt(key, b"tampered evidence bytes")
    _expect_artifact_error(
        "corrupted object",
        lambda: store.get_verified(key, recorded),
        "integrity-mismatch",
        problems,
    )
    # a VALID but divergent expectation is also a mismatch --
    # the recorded digest and the actual digest are surfaced.
    store.put(key, original)
    divergent = _sha256_hex(b"a different artifact entirely")
    try:
        store.get_verified(key, divergent)
    except R2ArtifactError as error:
        if error.reason_code != "integrity-mismatch":
            problems.append(
                "divergent expectation raised %r" % (error.reason_code,)
            )
        if recorded not in str(error) or divergent not in str(error):
            problems.append(
                "the mismatch detail does not surface both digests"
            )
    except Exception as error:  # noqa: BLE001
        problems.append("divergent expectation raised %r" % (error,))
    else:
        problems.append("a divergent expectation silently substituted")
    if problems:
        results.append(fail("08 integrity mismatch", "; ".join(problems)))
    else:
        results.append(
            ok(
                "08 integrity mismatch",
                "corrupted bytes and divergent expectations raise the typed "
                "integrity-mismatch (both digests surfaced); never a silent "
                "substitution",
            )
        )


def case_09_delete_get_after_delete(results: List[Result]) -> None:
    """delete removes the object bytes and returns the deletion
    reference; every follow-up read is the typed missing-object;
    re-deleting is idempotent (the S3-compatible semantics)."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    payload = b"doomed artifact bytes"
    key = "artifacts/2026-09-13/doomed.bin"
    store.put(key, payload)
    deletion = store.delete(key)
    if sorted(deletion) != ["backend", "deleted", "key"]:
        problems.append(
            "the deletion reference members drifted: %s" % (sorted(deletion),)
        )
    if deletion["key"] != key or deletion["backend"] != "r2":
        problems.append("the deletion reference key/backend drifted")
    if deletion["deleted"] is not True:
        problems.append("the deletion reference does not record the deletion")
    if fake.stored_bytes(key) is not None:
        problems.append("the object bytes survived the delete")
    _expect_artifact_error(
        "get after delete",
        lambda: store.get(key),
        "missing-object",
        problems,
    )
    _expect_artifact_error(
        "head after delete",
        lambda: store.head(key),
        "missing-object",
        problems,
    )
    _expect_artifact_error(
        "get_verified after delete",
        lambda: store.get_verified(key, _sha256_hex(payload)),
        "missing-object",
        problems,
    )
    again = store.delete(key)
    if again["deleted"] is not True:
        problems.append("re-delete is not idempotent")
    never = "artifacts/2026-09-13/never-existed.bin"
    if store.delete(never)["deleted"] is not True:
        problems.append("deleting a never-existing key raised")
    _expect_artifact_error(
        "empty delete key",
        lambda: store.delete(""),
        "config-invalid",
        problems,
    )
    deletes = [call for call in fake.calls if call[0] == "DELETE"]
    if len(deletes) != 3:
        problems.append("the DELETE wire discipline drifted: %r" % (deletes,))
    if fake.violations:
        problems.append("wire violations: %r" % (fake.violations,))
    if problems:
        results.append(fail("09 delete + get-after-delete", "; ".join(problems)))
    else:
        results.append(
            ok(
                "09 delete + get-after-delete",
                "delete returns the 3-member deletion reference; get/head/"
                "get_verified after delete are typed missing-object; "
                "re-delete and never-existed deletes are idempotent",
            )
        )


def case_10_backend_failure(results: List[Result]) -> None:
    """A dead transport and HTTP 400/409/429/5xx raise the typed
    backend-unavailable error; 401/403 are the frozen
    config-invalid credential-refusal mapping (still typed, still
    fail-closed); no silent success anywhere."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    key = "artifacts/2026-09-13/outage.bin"
    store.put(key, b"outage bytes")
    for operation_name, operation in (
        ("put", lambda: store.put("artifacts/2026-09-13/put-outage", b"x")),
        ("get", lambda: store.get(key)),
        ("head", lambda: store.head(key)),
        ("delete", lambda: store.delete(key)),
        (
            "get_verified",
            lambda: store.get_verified(key, _sha256_hex(b"outage bytes")),
        ),
    ):
        fake.raise_error = OSError("simulated r2 outage")
        _expect_artifact_error(
            "dead transport %s" % operation_name,
            operation,
            "backend-unavailable",
            problems,
        )
    for status in (400, 409, 429, 500, 502, 503, 504):
        fake.next_status = status
        _expect_artifact_error(
            "http %d" % status,
            lambda: store.get(key),
            "backend-unavailable",
            problems,
        )
    for status in (401, 403):
        fake.next_status = status
        _expect_artifact_error(
            "http %d (credentials refused)" % status,
            lambda: store.get(key),
            "config-invalid",
            problems,
        )
    if problems:
        results.append(fail("10 backend failure", "; ".join(problems)))
    else:
        results.append(
            ok(
                "10 backend failure",
                "dead transport and HTTP 400/409/429/5xx raise the typed "
                "backend-unavailable; 401/403 the frozen config-invalid "
                "credential refusal; no silent success",
            )
        )


def case_11_protocol_errors(results: List[Result]) -> None:
    """Successful responses lacking the S3 response headers (the
    ETag, the Content-Length) or carrying a non-numeric length
    raise the typed protocol-error -- a malformed success is
    never a silent success."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    fake.next_status = 200
    fake.next_headers = {}
    _expect_artifact_error(
        "PUT 200 without ETag",
        lambda: store.put("artifacts/2026-09-13/no-etag", b"data"),
        "protocol-error",
        problems,
    )
    fake.next_status = 200
    fake.next_headers = {"etag": '"d41d8cd98f00b204e9800998ecf8427e"'}
    _expect_artifact_error(
        "HEAD 200 without Content-Length",
        lambda: store.head("artifacts/2026-09-13/no-length"),
        "protocol-error",
        problems,
    )
    fake.next_status = 200
    fake.next_headers = {"content-length": "5"}
    _expect_artifact_error(
        "HEAD 200 without ETag",
        lambda: store.head("artifacts/2026-09-13/no-etag-head"),
        "protocol-error",
        problems,
    )
    fake.next_status = 200
    fake.next_headers = {
        "etag": '"abc"',
        "content-length": "twelve",
    }
    _expect_artifact_error(
        "HEAD 200 non-numeric Content-Length",
        lambda: store.head("artifacts/2026-09-13/bad-length"),
        "protocol-error",
        problems,
    )
    if problems:
        results.append(fail("11 protocol errors", "; ".join(problems)))
    else:
        results.append(
            ok(
                "11 protocol errors",
                "200s lacking ETag/Content-Length (or a non-numeric length) "
                "raise the typed protocol-error; a malformed success is "
                "never a silent success",
            )
        )


def case_12_sigv4_signing(results: List[Result]) -> None:
    """The Authorization header format (the Credential scope, the
    frozen SignedHeaders, the 64-hex signature), byte-identity
    against an INDEPENDENT re-derivation of the SigV4 chain,
    stability over identical inputs, input binding, and the
    fail-closed shapes of the signing seam."""
    problems: List[str] = []
    payload = b"battery signing payload"
    payload_hash = _sha256_hex(payload)
    key = "artifacts/evidence 01.bin"  # the space exercises encoding
    url, headers = r2_module._sign_request(  # noqa: SLF001 - the documented deterministic seam
        method="PUT",
        endpoint=_ENDPOINT,
        bucket=_BUCKET,
        key=key,
        account_id=_ACCOUNT_ID,
        access_key_id=_ACCESS_KEY_ID,
        secret_access_key=_SECRET_ACCESS_KEY,
        payload_hash=payload_hash,
        extra_headers={"Content-Type": "application/json"},
        amz_date=_AMZ_DATE,
    )
    expected_uri = "/%s/%s" % (quote(_BUCKET, safe=""), quote(key, safe="/"))
    if url != _ENDPOINT + expected_uri:
        problems.append("the object url is not the path-style encoded url")
    if headers.get("x-amz-date") != _AMZ_DATE:
        problems.append("the pinned x-amz-date was not carried")
    if headers.get("x-amz-content-sha256") != payload_hash:
        problems.append("the payload hash header drifted")
    if headers.get("Content-Type") != "application/json":
        problems.append("the unsigned extra header was not merged")
    authorization = headers.get("Authorization", "")
    if _AUTH_PATTERN.match(authorization) is None:
        problems.append("the Authorization header format is malformed")
    expected_authorization = _independent_authorization(
        method="PUT",
        host=_HOST,
        canonical_uri=expected_uri,
        payload_hash=payload_hash,
        amz_date=_AMZ_DATE,
        access_key_id=_ACCESS_KEY_ID,
        secret_access_key=_SECRET_ACCESS_KEY,
    )
    if authorization != expected_authorization:
        problems.append(
            "the Authorization header is not byte-identical to the "
            "independent re-derivation"
        )

    def signed(**overrides: Any) -> Tuple[str, Dict[str, str]]:
        parameters: Dict[str, Any] = {
            "method": "PUT",
            "endpoint": _ENDPOINT,
            "bucket": _BUCKET,
            "key": key,
            "account_id": _ACCOUNT_ID,
            "access_key_id": _ACCESS_KEY_ID,
            "secret_access_key": _SECRET_ACCESS_KEY,
            "payload_hash": payload_hash,
            "extra_headers": {"Content-Type": "application/json"},
            "amz_date": _AMZ_DATE,
        }
        parameters.update(overrides)
        _url, _headers = r2_module._sign_request(**parameters)  # noqa: SLF001
        return _url, _headers

    # stability: identical inputs -> identical bytes
    url_again, headers_again = signed()
    if (url_again, headers_again) != (url, headers):
        problems.append("signing is not stable over identical inputs")
    # input binding: the signature covers method/key/payload/date
    baseline = _signature_of(headers["Authorization"])
    varied = {
        "method": ("GET",),
        "key": ("artifacts/evidence 02.bin",),
        "payload_hash": (_sha256_hex(b"other payload"),),
        "amz_date": ("20260913T000001Z",),
        "bucket": ("adcos-artifacts-battery-2",),
    }
    for name, (value,) in varied.items():
        _varied_url, varied_headers = signed(**{name: value})
        if _signature_of(varied_headers["Authorization"]) == baseline:
            problems.append("the signature does not bind %s" % (name,))
    # fail-closed shapes of the signing seam
    def _seam_invalid(override_name: str, override_value: Any) -> None:
        parameters: Dict[str, Any] = {
            "method": "PUT",
            "endpoint": _ENDPOINT,
            "bucket": _BUCKET,
            "key": key,
            "account_id": _ACCOUNT_ID,
            "access_key_id": _ACCESS_KEY_ID,
            "secret_access_key": _SECRET_ACCESS_KEY,
            "payload_hash": payload_hash,
            "extra_headers": None,
            "amz_date": _AMZ_DATE,
        }
        parameters[override_name] = override_value
        _expect_artifact_error(
            "signing seam %s=%r" % (override_name, override_value),
            lambda parameters=parameters: r2_module._sign_request(  # noqa: SLF001
                **parameters
            ),
            "config-invalid",
            problems,
        )

    for name, value in (
        ("method", "PATCH"),
        ("endpoint", "http://%s" % _HOST),
        ("endpoint", "https://other-account.r2.cloudflarestorage.com"),
        ("amz_date", "2026-09-13T00:00:00Z"),
        ("payload_hash", "not-hex"),
        ("account_id", ""),
        ("access_key_id", ""),
        ("secret_access_key", ""),
        ("bucket", "under_score"),
        ("extra_headers", "not-a-mapping"),
    ):
        _seam_invalid(name, value)
    # store-level: every public operation carried the well-formed
    # Authorization on the wire (the fake validated each call).
    fake = _world()
    store = _store(fake)
    wire_key = "artifacts/2026-09-13/wire.bin"
    store.put(wire_key, b"wire bytes")
    store.get(wire_key)
    store.head(wire_key)
    store.get_verified(wire_key, _sha256_hex(b"wire bytes"))
    store.delete(wire_key)
    if fake.violations:
        problems.append("wire violations: %r" % (fake.violations,))
    if problems:
        results.append(fail("12 SigV4 signing", "; ".join(problems)))
    else:
        results.append(
            ok(
                "12 SigV4 signing",
                "Authorization format pinned (Credential <access>/<date>/"
                "auto/s3/aws4_request, SignedHeaders host;x-amz-content-"
                "sha256;x-amz-date, 64-hex signature); byte-identical to an "
                "independent re-derivation; stable and input-bound "
                "(signature digest %s)"
                % baseline[:16],
            )
        )


def case_13_secret_hygiene(results: List[Result]) -> None:
    """The access key id and the secret access key never appear
    in any error surface or string representation of failures
    (the Authorization wire header is their sole carrier, by
    SigV4 design)."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    key = "artifacts/2026-09-13/hygiene.bin"
    store.put(key, b"hygiene bytes")
    recorded = _sha256_hex(b"hygiene bytes")
    fake.corrupt(key, b"tampered bytes")
    surfaces: List[str] = []

    def collect(operation) -> None:
        try:
            operation()
        except R2ArtifactError as error:
            surfaces.append("%s|%s|%r" % (str(error), error.detail, error))
        except Exception as error:  # noqa: BLE001
            problems.append("unexpected error %r" % (error,))
        else:
            problems.append("an operation silently succeeded")

    for operation in (
        lambda: store.get(key),
        lambda: store.put("artifacts/2026-09-13/x", b"x"),
        lambda: store.head(key),
        lambda: store.delete(key),
    ):
        fake.raise_error = OSError("simulated r2 outage")
        collect(operation)
    fake.raise_error = None
    fake.next_status = 500
    collect(lambda: store.get(key))
    fake.next_status = 401
    collect(lambda: store.get(key))
    fake.next_status = 404
    collect(lambda: store.get(key))
    fake.next_status = 200
    fake.next_headers = {}
    collect(lambda: store.put("artifacts/2026-09-13/y", b"y"))
    collect(lambda: store.get_verified(key, recorded))
    collect(lambda: store.get("artifacts/2026-09-13/absent"))
    for secret in (_ACCESS_KEY_ID, _SECRET_ACCESS_KEY):
        for rendered in surfaces:
            if secret in rendered:
                problems.append(
                    "secret leaked into an error surface: %r"
                    % (rendered[:40],)
                )
    if _ACCESS_KEY_ID in fake.violations or _SECRET_ACCESS_KEY in "".join(
        fake.violations
    ):
        problems.append("a secret reached the fake's audit log")
    if fake.violations:
        problems.append("wire violations: %r" % (fake.violations,))
    if len(surfaces) < 9:
        problems.append("the failure-surface sweep was too thin")
    if problems:
        results.append(fail("13 secret hygiene", "; ".join(problems)))
    else:
        results.append(
            ok(
                "13 secret hygiene",
                "access key id and secret absent from all %d collected "
                "failure surfaces (exception str/detail/repr); the "
                "Authorization wire header is their sole carrier"
                % len(surfaces),
            )
        )


def case_14_determinism(results: List[Result]) -> None:
    """Identical traces produce identical references, wire logs
    and typed-failure reasons across fresh worlds (no wall clock
    and no randomness is ever recorded); the deterministic key
    allocator yields a unique key per put, stable per
    construction position (the digest in the case detail pins
    byte-identity for the x3 runs)."""
    problems: List[str] = []

    def scenario() -> Tuple[Any, ...]:
        fake = _world()
        store = _store(fake)
        trace: List[Any] = []
        payloads = (
            b"",
            b"adcos-artifact",
            b"\x00\xff\x00 binary \n\r bytes",
            "unicode-\u00e9vidence-\u2713".encode("utf-8"),
            b"x" * 4096,
        )
        for sequence, payload in enumerate(payloads):
            key = _auto_key(payload, sequence)
            trace.append(store.put(key, payload))
            trace.append(_sha256_hex(store.get(key)))
            trace.append(store.head(key))
        try:
            store.get("artifacts/2026-09-13/never-put")
        except R2ArtifactError as error:
            trace.append(("typed", error.reason_code))
        tampered_key = _auto_key(payloads[1], 1)
        fake.corrupt(tampered_key, b"tampered")
        try:
            store.get_verified(
                tampered_key, _sha256_hex(payloads[1])
            )
        except R2ArtifactError as error:
            trace.append(("typed", error.reason_code))
        deleted_key = _auto_key(payloads[2], 2)
        trace.append(store.delete(deleted_key))
        try:
            store.get(deleted_key)
        except R2ArtifactError as error:
            trace.append(("typed", error.reason_code))
        trace.append(tuple(fake.calls))
        trace.append(tuple(fake.signed_payload_hashes))
        trace.append(tuple(sorted(fake.objects)))
        return tuple(trace)

    first, second = scenario(), scenario()
    if first != second:
        problems.append("the scenario traces diverged across fresh worlds")
    # the deterministic key allocator: unique per put (40 puts,
    # 40 distinct keys -- a collision would corrupt the artifact
    # boundary), stable per construction position.
    keys = [
        _auto_key(b"payload-%d" % index, index) for index in range(40)
    ]
    if len(set(keys)) != 40:
        problems.append("the auto-generated keys collided")
    if _auto_key(b"same payload", 0) != _auto_key(b"same payload", 0):
        problems.append("the auto-generated keys are not stable")
    if _auto_key(b"same payload", 0) == _auto_key(b"same payload", 1):
        problems.append("the sequence position does not bind the key")
    if _auto_key(b"payload-a", 0) == _auto_key(b"payload-b", 0):
        problems.append("the content digest does not bind the key")
    trace_digest = hashlib.sha256(
        repr(first).encode("utf-8")
    ).hexdigest()[:16]
    if problems:
        results.append(fail("14 determinism", "; ".join(problems)))
    else:
        results.append(
            ok(
                "14 determinism",
                "identical traces across fresh worlds (trace digest %s "
                "pinned); the content+sequence key allocator gives every "
                "put a unique key" % trace_digest,
            )
        )


def case_15_metadata_boundary(results: List[Result]) -> None:
    """The metadata-boundary contract: put returns ONLY a
    reference (exactly key/size/content_sha256/etag/backend -- no
    state authority beyond it); the object store holds only the
    object bytes; reads return raw bytes, not metadata
    envelopes; the durable side owns key allocation."""
    problems: List[str] = []
    fake = _world()
    store = _store(fake)
    payload = b"boundary payload"
    key = "artifacts/2026-09-13/boundary.bin"
    reference = store.put(key, payload)
    if sorted(reference) != [
        "backend",
        "content_sha256",
        "etag",
        "key",
        "size",
    ]:
        problems.append("the ArtifactRef carries extra members")
    for member, value in reference.items():
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            problems.append(
                "the reference member %r is not a plain primitive" % (member,)
            )
    state_authority_members = (
        "contract",
        "state",
        "journal",
        "record",
        "evidence",
        "namespace",
        "sequence",
        "version",
        "ttl",
        "owner",
        "token",
    )
    for member in state_authority_members:
        if member in reference:
            problems.append(
                "the reference carries the state-authority member %r"
                % (member,)
            )
    if fake.stored_bytes(key) != payload:
        problems.append("the object store holds more than the object bytes")
    fetched = store.get(key)
    if isinstance(fetched, dict) or isinstance(fetched, list):
        problems.append("get returned a metadata envelope, not raw bytes")
    if store.bucket != _BUCKET:
        problems.append("the public bucket property drifted")
    # the adapter takes no key-minting authority: an explicit key
    # is REQUIRED for every object operation (the durable side
    # allocates keys; pinned as config-invalid in case 02).
    _expect_artifact_error(
        "put without an explicit key",
        lambda: store.put("", b"anonymous"),
        "config-invalid",
        problems,
    )
    if fake.violations:
        problems.append("wire violations: %r" % (fake.violations,))
    if problems:
        results.append(fail("15 metadata boundary", "; ".join(problems)))
    else:
        results.append(
            ok(
                "15 metadata boundary",
                "the reference carries exactly key/size/checksum/etag/"
                "backend (plain primitives, no state authority); the store "
                "holds only the object bytes; reads return raw bytes; key "
                "allocation stays durable-side",
            )
        )


_CASES = (
    case_01_module_surface,
    case_02_config_invalid,
    case_03_put_reference,
    case_04_get_round_trip,
    case_05_get_verified_success,
    case_06_checksum_discipline,
    case_07_missing_object,
    case_08_integrity_mismatch,
    case_09_delete_get_after_delete,
    case_10_backend_failure,
    case_11_protocol_errors,
    case_12_sigv4_signing,
    case_13_secret_hygiene,
    case_14_determinism,
    case_15_metadata_boundary,
)


def main() -> int:
    results: List[Result] = []
    for case in _CASES:
        try:
            case(results)
        except Exception as error:  # noqa: BLE001 - the battery never crashes silently
            results.append(
                fail(case.__name__, "raised: %r" % (error,))
            )
    width = max(len(name) for name, _ok, _detail in results)
    passed = 0
    for name, is_ok, detail in results:
        marker = "ok  " if is_ok else "FAIL"
        print("[%s] %-*s %s" % (marker, width, name, detail))
        if is_ok:
            passed += 1
    print("-" * 72)
    print(
        "Result: %s (%d/%d cases passed)"
        % (
            "PASS" if passed == len(results) else "FAIL",
            passed,
            len(results),
        )
    )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
