"use client";

/**
 * VerbatimNote — a backend note rendered exactly as sent (the assurance
 * and usage reads carry the backend's own honesty notes; they are part
 * of the resource, never paraphrased away).
 */

export function VerbatimNote({
  note,
  label,
}: {
  note: string | null | undefined;
  label: string;
}) {
  if (note === null || note === undefined || note.length === 0) return null;
  return (
    <blockquote
      data-testid="verbatim-note"
      className="rounded-md border border-line bg-raised px-3 py-2"
    >
      <p className="font-mono text-2xs uppercase tracking-wide text-ink-faint">
        {label}
      </p>
      <p className="mt-1 text-sm leading-relaxed text-ink-muted">{note}</p>
    </blockquote>
  );
}
