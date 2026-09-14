/**
 * The shared placeholder surface for areas owned by Workers 2/3.
 *
 * Mirrors the home page's structure exactly (workbench container, header,
 * then a bordered surface card listing the area's intended content map
 * from the FROZEN UX spec) so the console keeps one visual language
 * while areas are being implemented. Pure presentational — usable from
 * server components.
 */

export interface ContentMapEntry {
  title: string;
  description: string;
}

export interface AreaPlaceholderProps {
  title: string;
  /** e.g. "This area is being implemented (Worker 2)." */
  intro: string;
  map: ContentMapEntry[];
}

export function AreaPlaceholder({ title, intro, map }: AreaPlaceholderProps) {
  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <header className="mb-6">
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="mt-1 text-sm text-ink-muted">{intro}</p>
      </header>

      <section
        aria-labelledby={`${title.toLowerCase()}-content-map`}
        className="rounded-md border border-line bg-surface"
      >
        <h2
          id={`${title.toLowerCase()}-content-map`}
          className="border-b border-line px-4 py-3 text-sm font-semibold"
        >
          Intended content map (from the frozen UX spec)
        </h2>
        <ul className="divide-y divide-line">
          {map.map((entry) => (
            <li key={entry.title} className="px-4 py-3">
              <p className="text-sm font-medium">{entry.title}</p>
              <p className="mt-0.5 text-sm text-ink-muted">{entry.description}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
