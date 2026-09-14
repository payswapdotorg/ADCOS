/**
 * CodeBlock — calm mono block for code, curl reproductions and
 * verbatim payloads. Pure render (the copy affordance is the
 * client-side CopyButton), so it works from server components.
 */

import { cn } from "@/lib/utils";
import { CopyButton } from "./copy-button";

export function CodeBlock({
  code,
  language,
  filename,
  className,
}: {
  code: string;
  language?: string;
  filename?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-md border border-line bg-raised",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-line px-2 py-1">
        <div className="flex min-w-0 items-center gap-2">
          {filename ? (
            <span className="truncate font-mono text-2xs text-ink-muted">
              {filename}
            </span>
          ) : null}
          {language ? (
            <span className="font-mono uppercase text-2xs text-ink-faint">
              {language}
            </span>
          ) : null}
        </div>
        <CopyButton value={code} ariaLabel="Copy code" label="Copy" />
      </div>
      <pre className="overflow-x-auto whitespace-pre p-3 font-mono text-xs leading-relaxed text-ink">
        <code>{code}</code>
      </pre>
    </div>
  );
}
