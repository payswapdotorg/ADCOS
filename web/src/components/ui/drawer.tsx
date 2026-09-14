"use client";

/**
 * Drawer — the Radix Dialog side panel. Focus trapping, Escape close
 * and focus restoration come from @radix-ui/react-dialog; the styling
 * is the console's overlay surface with a hairline edge.
 */

import type { ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { cn } from "@/lib/utils";
import { CloseIcon } from "./icons";

export function Drawer({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  side = "right",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  side?: "right" | "left";
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-canvas/80" />
        <Dialog.Content
          className={cn(
            "fixed bottom-0 top-0 z-50 flex w-[480px] max-w-[90vw] flex-col bg-overlay",
            side === "right"
              ? "right-0 border-l border-line"
              : "left-0 border-r border-line",
          )}
        >
          <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
            <div className="min-w-0">
              <Dialog.Title className="text-sm font-semibold text-ink">
                {title}
              </Dialog.Title>
              <Dialog.Description
                className={cn(
                  "text-xs text-ink-muted",
                  !description && "sr-only",
                )}
              >
                {description ?? ""}
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close panel"
                className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-ink-faint transition-colors hover:bg-raised hover:text-ink"
              >
                <CloseIcon size={16} />
              </button>
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
            {children}
          </div>
          {footer ? (
            <div className="flex items-center justify-end gap-2 border-t border-line px-4 py-3">
              {footer}
            </div>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
