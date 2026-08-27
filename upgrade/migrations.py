"""Reversible schema migrations for versioned persisted state (WORK-029).

The Schema Version line (governance section 3 kind 3): each persisted
artifact carries its own ``MAJOR.MINOR`` schema version; additive
evolution bumps the minor, breaking changes bump the major.  This
registry walks a deterministic chain of migration steps between two
versions of one artifact's state and -- the WORK-029 acceptance
criterion -- the walk is REVERSIBLE:

- every step declares ``reversible`` honestly;
- reversing a declared non-reversible step fails closed
  (``MIGRATION_NOT_REVERSIBLE`` -- never a best-effort partial undo);
- a chain is reversible iff every edge on it is reversible, and the
  upgrade manager only accepts plans whose COMPLETE chain is
  reversible (a staged upgrade that cannot be rolled back is not a
  staged upgrade -- it is a flag day).

Discipline:

- step shapes are enforced at descriptor construction (additive =
  exactly one minor bump; breaking = exactly one major bump, minor
  reset to 0), so the registry graph is a well-formed version line;
- the registry stores FORWARD edges only; the backward walk reuses
  the same edge's backward function (a separately registered
  downgrade edge is not constructible);
- duplicate edges are rejected (``MIGRATION_DUPLICATE_EDGE``);
- an unknown path fails closed (``MIGRATION_PATH_UNKNOWN`` -- never
  a silent identity "migration");
- every step function must return a Mapping
  (``MIGRATION_INVALID_STEP`` otherwise);
- state dicts are passed through untouched when the caller's state
  is already at the target version only in the degenerate
  from == to case, which is itself rejected: no-op migrations do not
  exist (a migration CHANGES the schema version).

Migration functions are required to be PURE: deterministic
dict-in/dict-out with no side effects on the input mapping.  The
self-test proves input immutability and round-trip identity
(forward then backward is byte-identical to the original canonical
state) for every reversible chain it exercises.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from .errors import UpgradeError, UpgradeReasonCode
from .model import MigrationDescriptor
from .validation import parse_dotted_pair

#: A forward/backward migration function: pure dict-in / dict-out.
MigrationFn = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class Migration:
    """One executable migration step: descriptor + forward/backward."""

    __slots__ = ("descriptor", "forward", "backward")

    def __init__(
        self,
        descriptor: MigrationDescriptor,
        forward: MigrationFn,
        backward: MigrationFn,
    ) -> None:
        if not isinstance(descriptor, MigrationDescriptor):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "Migration requires a MigrationDescriptor (got %s)"
                % (type(descriptor).__name__,),
            )
        if not callable(forward) or not callable(backward):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "Migration forward/backward must be callables",
            )
        self.descriptor = descriptor
        self.forward = forward
        self.backward = backward


def _edge_key(schema_id: str, from_version: str, to_version: str) -> Tuple[str, str, str]:
    return (schema_id, from_version, to_version)


class MigrationRegistry:
    """The deterministic, fail-closed migration graph.

    Edges are keyed ``(schema_id, from_version, to_version)``; path
    resolution is BFS over lexicographically sorted adjacency (fewest
    edges, deterministic order -- no dict-iteration-order dependence).
    """

    def __init__(self) -> None:
        self._edges: Dict[Tuple[str, str, str], Migration] = {}

    # -- registration -------------------------------------------------

    def register(self, migration: Migration) -> MigrationDescriptor:
        """Register one migration edge; duplicates fail closed."""
        descriptor = migration.descriptor
        key = _edge_key(descriptor.schema_id, descriptor.from_version, descriptor.to_version)
        if key in self._edges:
            raise UpgradeError(
                UpgradeReasonCode.MIGRATION_DUPLICATE_EDGE,
                "migration edge %s %s -> %s is already registered"
                % (descriptor.schema_id, descriptor.from_version, descriptor.to_version),
            )
        self._edges[key] = migration
        return descriptor

    def register_step(
        self,
        schema_id: str,
        from_version: str,
        to_version: str,
        reversible: bool,
        breaking: bool,
        forward: MigrationFn,
        backward: MigrationFn,
    ) -> MigrationDescriptor:
        """Convenience constructor+register in one call."""
        return self.register(
            Migration(
                MigrationDescriptor(
                    schema_id=schema_id, from_version=from_version,
                    to_version=to_version, reversible=reversible, breaking=breaking,
                ),
                forward=forward, backward=backward,
            )
        )

    # -- introspection ------------------------------------------------

    def edge_count(self) -> int:
        return len(self._edges)

    def descriptors(self) -> Tuple[MigrationDescriptor, ...]:
        """All registered descriptors in canonical (schema, from, to)
        order (deterministic introspection)."""
        return tuple(
            self._edges[key].descriptor
            for key in sorted(self._edges)
        )

    def _adjacency(self, schema_id: str) -> Dict[str, Tuple[Tuple[str, str], ...]]:
        adjacency: Dict[str, Tuple[Tuple[str, str], ...]] = {}
        for key in sorted(self._edges):
            edge_schema, source, target = key
            if edge_schema != schema_id:
                continue
            adjacency.setdefault(source, ())
            adjacency[source] = adjacency[source] + ((target, key),)
        return adjacency

    # -- path resolution ----------------------------------------------

    def _forward_path(
        self, schema_id: str, from_version: str, to_version: str,
    ) -> Tuple[MigrationDescriptor, ...]:
        """The deterministic FORWARD chain ``from -> to`` (from < to):
        BFS over sorted adjacency -- the fewest-edge path, and among
        equal-length paths the lexicographically smallest step
        sequence.  Unknown target => ``MIGRATION_PATH_UNKNOWN``."""
        adjacency = self._adjacency(schema_id)
        # BFS: frontier of (version, path-of-edge-keys)
        frontier: Tuple[Tuple[str, Tuple[Tuple[str, str, str], ...]], ...] = (
            (from_version, ()),
        )
        visited = {from_version}
        while frontier:
            next_frontier = []
            for version, edge_keys in frontier:
                for target, key in sorted(adjacency.get(version, ())):
                    if target in visited:
                        continue
                    extended = edge_keys + (key,)
                    if target == to_version:
                        return tuple(self._edges[k].descriptor for k in extended)
                    visited.add(target)
                    next_frontier.append((target, extended))
            frontier = tuple(next_frontier)
        raise UpgradeError(
            UpgradeReasonCode.MIGRATION_PATH_UNKNOWN,
            "no migration path %s %s -> %s is registered (unknown paths "
            "fail closed; there is no identity 'migration')"
            % (schema_id, from_version, to_version),
        )

    def path(
        self, schema_id: str, from_version: str, to_version: str,
    ) -> Tuple[MigrationDescriptor, ...]:
        """The deterministic migration chain linking two versions.

        The registry stores FORWARD edges only (a downgrade edge is
        not constructible: step shapes always increase the version).
        A backward request ``from > to`` resolves to the FORWARD
        chain ``to -> from`` -- the edges that a backward walk will
        traverse in reverse.  ``from == to`` is a rejected no-op:
        migrations change the schema version, they never re-stamp
        it.
        """
        parse_dotted_pair(from_version, "path from_version")
        parse_dotted_pair(to_version, "path to_version")
        source = parse_dotted_pair(from_version, "path from_version")
        target = parse_dotted_pair(to_version, "path to_version")
        if source == target:
            raise UpgradeError(
                UpgradeReasonCode.MIGRATION_INVALID_STEP,
                "migration path %s -> %s is a no-op: migrations change the "
                "schema version, they never re-stamp it"
                % (from_version, to_version),
            )
        if target > source:
            return self._forward_path(schema_id, from_version, to_version)
        return self._forward_path(schema_id, to_version, from_version)

    def path_is_reversible(
        self, schema_id: str, from_version: str, to_version: str,
    ) -> bool:
        """True iff every edge on the chain linking the two versions
        (either direction) is reversible."""
        return all(
            descriptor.reversible
            for descriptor in self.path(schema_id, from_version, to_version)
        )

    # -- execution ----------------------------------------------------

    def _apply(
        self,
        state: Mapping[str, Any],
        schema_id: str,
        from_version: str,
        to_version: str,
        backward: bool,
    ) -> Mapping[str, Any]:
        source = parse_dotted_pair(from_version, "migrate from_version")
        target = parse_dotted_pair(to_version, "migrate to_version")
        if not backward and target < source:
            raise UpgradeError(
                UpgradeReasonCode.MIGRATION_INVALID_STEP,
                "forward migration %s %s -> %s must increase the version "
                "(a decrease is a backward migration)"
                % (schema_id, from_version, to_version),
            )
        if backward and target > source:
            raise UpgradeError(
                UpgradeReasonCode.MIGRATION_INVALID_STEP,
                "backward migration %s %s -> %s must decrease the version "
                "(an increase is a forward migration)"
                % (schema_id, from_version, to_version),
            )
        # Both directions resolve the FORWARD chain linking the two
        # versions; the backward walk traverses it in reverse.
        descriptors = self.path(schema_id, from_version, to_version)
        if backward:
            reversible = [d for d in descriptors if not d.reversible]
            if reversible:
                first = reversible[0]
                raise UpgradeError(
                    UpgradeReasonCode.MIGRATION_NOT_REVERSIBLE,
                    "migration %s %s -> %s crosses the non-reversible step "
                    "%s -> %s (%s): declared non-reversible steps are never "
                    "reversed, not even partially"
                    % (
                        schema_id, from_version, to_version,
                        first.from_version, first.to_version, first.migration_id[:48],
                    ),
                )
            # Reverse order, backward functions.
            current: Mapping[str, Any] = state
            for descriptor in reversed(descriptors):
                migration = self._edges[
                    _edge_key(descriptor.schema_id, descriptor.from_version, descriptor.to_version)
                ]
                current = migration.backward(current)
                if not isinstance(current, Mapping):
                    raise UpgradeError(
                        UpgradeReasonCode.MIGRATION_INVALID_STEP,
                        "backward step %s %s -> %s returned %s (a Mapping is "
                        "required)"
                        % (
                            schema_id, descriptor.from_version,
                            descriptor.to_version, type(current).__name__,
                        ),
                    )
            return current
        current = state
        for descriptor in descriptors:
            migration = self._edges[
                _edge_key(descriptor.schema_id, descriptor.from_version, descriptor.to_version)
            ]
            current = migration.forward(current)
            if not isinstance(current, Mapping):
                raise UpgradeError(
                    UpgradeReasonCode.MIGRATION_INVALID_STEP,
                    "forward step %s %s -> %s returned %s (a Mapping is "
                    "required)"
                    % (
                        schema_id, descriptor.from_version,
                        descriptor.to_version, type(current).__name__,
                    ),
                )
        return current

    def migrate_forward(
        self,
        state: Mapping[str, Any],
        schema_id: str,
        from_version: str,
        to_version: str,
    ) -> Mapping[str, Any]:
        """Walk the forward path, applying each step's forward function."""
        return self._apply(state, schema_id, from_version, to_version, backward=False)

    def migrate_backward(
        self,
        state: Mapping[str, Any],
        schema_id: str,
        from_version: str,
        to_version: str,
    ) -> Mapping[str, Any]:
        """Walk the reverse path, applying each step's backward
        function; any non-reversible edge on the path fails closed."""
        return self._apply(state, schema_id, from_version, to_version, backward=True)

    def migrate(
        self,
        state: Mapping[str, Any],
        schema_id: str,
        from_version: str,
        to_version: str,
    ) -> Mapping[str, Any]:
        """Migrate in the direction implied by the version comparison
        (``to > from`` forward, ``to < from`` backward)."""
        source = parse_dotted_pair(from_version, "migrate from_version")
        target = parse_dotted_pair(to_version, "migrate to_version")
        if target > source:
            return self.migrate_forward(state, schema_id, from_version, to_version)
        return self.migrate_backward(state, schema_id, from_version, to_version)
