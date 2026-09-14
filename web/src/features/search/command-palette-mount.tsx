"use client";

/**
 * The palette mount — the ONLY place the palette is wired to the app.
 *
 * The AppShell owns the open state (Cmd/Ctrl+K + the top bar trigger);
 * this layer turns the command registry + the recents store into palette
 * items and builds the execute closures: navigation commands push the
 * router AND feed the recents store (so the palette self-seeds "Recent"
 * from real navigation), arbitrary commands run their `run()`, and
 * recent objects navigate to their href.
 */

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  CommandPalette,
  type PaletteItem,
} from "@/components/ui/command-palette";
import { CommandIcon } from "@/components/ui";
import { useCommands, type CommandRecord } from "./command-registry";
import { addRecent, useRecentObjects } from "./recent-objects";

export interface CommandPaletteMountProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function commandToItem(
  command: CommandRecord,
  navigate: (href: string) => void,
): PaletteItem {
  return {
    id: `command:${command.id}`,
    title: command.title,
    section: "commands",
    icon: command.icon ?? <CommandIcon className="h-3.5 w-3.5 text-ink-faint" />,
    keywords: command.keywords,
    href: command.href,
    onExecute: () => {
      if (command.href) {
        // the palette self-feeds: navigating seeds the recents store
        addRecent({
          kind: "route",
          id: command.href,
          label: command.title,
          href: command.href,
          at: new Date().toISOString(),
        });
        navigate(command.href);
        return;
      }
      command.run?.();
    },
  };
}

export function CommandPaletteMount({ open, onOpenChange }: CommandPaletteMountProps) {
  const router = useRouter();
  const commands = useCommands();
  const recents = useRecentObjects();

  const items = useMemo<PaletteItem[]>(() => {
    const navigate = (href: string) => router.push(href);
    return [
      ...commands.map((command) => commandToItem(command, navigate)),
      ...recents.map<PaletteItem>((recent) => ({
        id: `recent:${recent.href}`,
        title: recent.label,
        section: "recent",
        keywords: [recent.kind],
        href: recent.href,
        onExecute: () => navigate(recent.href),
      })),
    ];
    // router is stable in Next 15; recents/commands drive the memo
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [commands, recents, router]);

  return (
    <CommandPalette
      open={open}
      onOpenChange={onOpenChange}
      items={items}
      placeholder="Search commands and objects…"
    />
  );
}
