/**
 * EmptyState — the calm "nothing here" presentation used by tables,
 * panels and feature surfaces.
 */

import type { ReactNode } from "react";
import { InboxIcon } from "./icons";

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full border border-line text-ink-faint">
        {icon ?? <InboxIcon size={16} />}
      </div>
      <div className="text-sm font-medium text-ink">{title}</div>
      {description ? (
        <div className="max-w-sm text-sm text-ink-muted">{description}</div>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
