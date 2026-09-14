/**
 * ApiRequestPanel — renders a developer-boundary request exactly as it
 * was (or would be) sent, plus a curl reproduction. The backend's
 * method/path/header vocabulary is shown verbatim; the panel never
 * invents an endpoint shape.
 */

import { cn } from "@/lib/utils";
import { CodeBlock } from "./code-block";
import { CopyButton } from "./copy-button";
import { JsonViewer } from "./json-viewer";

export interface ApiRequestHeader {
  name: string;
  value: string;
}

function stringifyBody(body: unknown): string {
  if (typeof body === "string") return body;
  try {
    return JSON.stringify(body) ?? String(body);
  } catch {
    return String(body);
  }
}

/**
 * Build the curl reproduction for a request.
 *
 * - the path is used verbatim (relative, same-origin);
 * - `Content-Type: application/json` is included whenever a body is
 *   present (and any caller-supplied Content-Type wins);
 * - every header gets its own `-H` line, Content-Type first, the rest
 *   sorted by name;
 * - the body is serialized compactly with single quotes escaped.
 */
export function buildCurl({
  method,
  path,
  headers,
  body,
}: {
  method: string;
  path: string;
  headers?: ApiRequestHeader[];
  body?: unknown;
}): string {
  const parts: string[] = [`curl -X ${method.toUpperCase()} '${path}'`];
  const hasBody = body !== undefined && body !== null;

  const all: ApiRequestHeader[] = [...(headers ?? [])];
  if (
    hasBody &&
    !all.some((header) => header.name.toLowerCase() === "content-type")
  ) {
    all.push({ name: "Content-Type", value: "application/json" });
  }
  const contentType = all.filter(
    (header) => header.name.toLowerCase() === "content-type",
  );
  const rest = all
    .filter((header) => header.name.toLowerCase() !== "content-type")
    .sort((a, b) => a.name.localeCompare(b.name));
  for (const header of [...contentType, ...rest]) {
    parts.push(`-H '${header.name}: ${header.value}'`);
  }

  if (hasBody) {
    parts.push(`--data-raw '${stringifyBody(body).replace(/'/g, "\\'")}'`);
  }

  return parts.join(" \\\n  ");
}

function MethodChip({ method }: { method: string }) {
  const upper = method.toUpperCase();
  const read =
    upper === "GET" || upper === "HEAD" || upper === "OPTIONS";
  return (
    <span
      data-testid="api-method-chip"
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-px font-mono uppercase tracking-wide",
        read
          ? "border-line-strong text-ink-muted"
          : "border-accent bg-accent text-accent-ink",
      )}
    >
      {upper}
    </span>
  );
}

export function ApiRequestPanel({
  method,
  path,
  headers,
  body,
  description,
  variant = "full",
}: {
  method: string;
  path: string;
  headers?: ApiRequestHeader[];
  body?: unknown;
  description?: string;
  variant?: "full" | "compact";
}) {
  const curl = buildCurl({ method, path, headers, body });

  if (variant === "compact") {
    return (
      <div className="flex items-center gap-2 rounded-md border border-line bg-raised px-2 py-1.5">
        <MethodChip method={method} />
        <span
          className="min-w-0 flex-1 truncate font-mono text-xs text-ink"
          title={path}
        >
          {path}
        </span>
        <CopyButton value={curl} ariaLabel="Copy curl command" label="curl" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {description ? (
        <p className="text-xs text-ink-muted">{description}</p>
      ) : null}
      <div className="flex items-center gap-2 rounded-md border border-line bg-raised px-2 py-1.5">
        <MethodChip method={method} />
        <span className="min-w-0 flex-1 break-all font-mono text-xs text-ink">
          {path}
        </span>
      </div>
      {headers && headers.length > 0 ? (
        <dl className="flex flex-col gap-1 rounded-md border border-line bg-raised px-2 py-1.5">
          {headers.map((header) => (
            <div
              key={header.name}
              className="grid grid-cols-[minmax(96px,auto)_1fr] gap-x-3"
            >
              <dt
                className="truncate font-mono text-2xs text-ink-faint"
                title={header.name}
              >
                {header.name}
              </dt>
              <dd className="break-all font-mono text-xs text-ink">
                {header.value}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
      {body !== undefined && body !== null ? (
        typeof body === "string" ? (
          <CodeBlock code={body} />
        ) : (
          <JsonViewer value={body} name="body" defaultExpandedDepth={1} />
        )
      ) : null}
      <CodeBlock code={curl} language="bash" />
    </div>
  );
}
