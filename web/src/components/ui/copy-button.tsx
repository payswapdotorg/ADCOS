"use client";

/**
 * CopyButton — the shared copy affordance (JsonViewer, CodeBlock,
 * ApiRequestPanel). Shows Copy→Check feedback for 1.5s and degrades
 * silently when the clipboard API is unavailable.
 */

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { CheckIcon, CopyIcon } from "./icons";

const FEEDBACK_MS = 1500;

export function CopyButton({
  value,
  label,
  ariaLabel,
  className,
}: {
  value: string;
  /** Optional visible label ("Copy"); swaps to "Copied" on success. */
  label?: string;
  ariaLabel: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  async function handleCopy() {
    // clipboard may be absent (insecure context / permissions): stay calm
    if (typeof navigator.clipboard?.writeText !== "function") return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), FEEDBACK_MS);
    } catch {
      // a rejected write leaves no feedback — never a thrown render
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={ariaLabel}
      className={cn(
        "inline-flex h-6 shrink-0 items-center gap-1 rounded-md px-1.5 font-mono text-2xs text-ink-faint transition-colors hover:bg-raised hover:text-ink",
        className,
      )}
    >
      {copied ? (
        <CheckIcon size={14} className="text-positive" />
      ) : (
        <CopyIcon size={14} />
      )}
      {label ? <span>{copied ? "Copied" : label}</span> : null}
    </button>
  );
}
