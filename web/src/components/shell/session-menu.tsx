"use client";

/**
 * The session menu — the application identity surface.
 *
 * Trigger shows the connected application (name + status dot) or the
 * connect affordance. The connected menu exposes the real application
 * profile (id with copy, capabilities count, valid_until), disconnect,
 * and the theme toggle; the disconnected menu opens the connect dialog.
 * The caption states the persistence contract honestly: in-memory only.
 */

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useEffect, useState } from "react";
import {
  CheckIcon,
  ChevronDownIcon,
  ConnectivityIcon,
  CopyIcon,
} from "@/components/ui";
import { useTheme } from "@/lib/design/theme";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { ConnectDialog } from "./connect-dialog";

const ITEM_CLASS =
  "flex cursor-pointer select-none items-center gap-2 rounded px-2 py-1.5 text-sm text-ink-muted outline-none data-[highlighted]:bg-raised data-[highlighted]:text-ink";

export function SessionMenu() {
  const { status, application, disconnect } = useSession();
  const { theme, toggleTheme } = useTheme();
  const [connectOpen, setConnectOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const connected = status === "connected";

  // reset the copied affordance when the session identity changes
  useEffect(() => {
    setCopied(false);
  }, [application?.application_id]);

  async function copyApplicationId(): Promise<void> {
    if (!application) return;
    try {
      await navigator.clipboard.writeText(application.application_id);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const themeLabel = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";

  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={connected ? `Application session: ${application?.application_name}` : "Connect application"}
            className="flex h-8 max-w-56 items-center gap-2 rounded border border-line bg-raised px-2.5 text-sm text-ink-muted hover:border-line-strong hover:text-ink"
          >
            {connected ? (
              <>
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current text-positive" />
                <span className="truncate font-mono text-xs">
                  {application?.application_name}
                </span>
              </>
            ) : (
              <>
                <ConnectivityIcon className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">Connect application</span>
              </>
            )}
            <ChevronDownIcon className="h-3 w-3 shrink-0 text-ink-faint" />
          </button>
        </DropdownMenu.Trigger>

        <DropdownMenu.Portal>
          <DropdownMenu.Content
            sideOffset={6}
            align="end"
            className="z-50 min-w-64 rounded-md border border-line bg-overlay p-1 shadow-[var(--shadow-panel)]"
          >
            {connected && application ? (
              <>
                <div className="px-2 py-2">
                  <p className="truncate font-mono text-xs text-ink">
                    {application.application_name}
                  </p>
                  <div className="mt-1 flex items-center gap-1.5">
                    <p className="truncate font-mono text-2xs text-ink-faint">
                      {application.application_id}
                    </p>
                    <button
                      type="button"
                      onClick={copyApplicationId}
                      aria-label="Copy application id"
                      title="Copy application id"
                      className="shrink-0 rounded p-0.5 text-ink-faint hover:text-ink"
                    >
                      {copied ? (
                        <CheckIcon className="h-3 w-3 text-positive" />
                      ) : (
                        <CopyIcon className="h-3 w-3" />
                      )}
                    </button>
                  </div>
                  <p className="mt-1 text-2xs text-ink-faint">
                    {application.capabilities.length}{" "}
                    {application.capabilities.length === 1 ? "capability" : "capabilities"}
                  </p>
                  <p className="text-2xs text-ink-faint">
                    valid until {application.valid_until}
                  </p>
                </div>
                <DropdownMenu.Separator className="my-1 h-px bg-line" />
                <DropdownMenu.Item className={ITEM_CLASS} onSelect={() => void copyApplicationId()}>
                  <CopyIcon className="h-3.5 w-3.5" />
                  Copy application id
                </DropdownMenu.Item>
                <DropdownMenu.Item
                  className={cn(ITEM_CLASS, "text-danger data-[highlighted]:bg-danger/10 data-[highlighted]:text-danger")}
                  onSelect={disconnect}
                >
                  Disconnect
                </DropdownMenu.Item>
                <DropdownMenu.Item className={ITEM_CLASS} onSelect={toggleTheme}>
                  {themeLabel}
                </DropdownMenu.Item>
              </>
            ) : (
              <>
                <DropdownMenu.Item className={ITEM_CLASS} onSelect={() => setConnectOpen(true)}>
                  <ConnectivityIcon className="h-3.5 w-3.5" />
                  Connect application…
                </DropdownMenu.Item>
                <DropdownMenu.Item className={ITEM_CLASS} onSelect={toggleTheme}>
                  {themeLabel}
                </DropdownMenu.Item>
              </>
            )}
            <DropdownMenu.Separator className="my-1 h-px bg-line" />
            <p className="px-2 pb-1.5 text-2xs text-ink-faint">
              Session is in-memory only — reloading clears it
            </p>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      <ConnectDialog open={connectOpen} onOpenChange={setConnectOpen} />
    </>
  );
}
