"use client";

/**
 * The primary navigation rail.
 *
 * Fixed-width (224px at `lg` and up, 56px icon-only below), one entry per
 * console area, active route marked with `aria-current="page"` and the
 * teal left border. The nav vocabulary matches the command registry's
 * "Navigate" group exactly — one mental model for mouse and keyboard.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";
import {
  AssuranceIcon,
  ConnectivityIcon,
  DevelopersIcon,
  EvidenceIcon,
  FulfillmentIcon,
  HomeIcon,
  NetworksIcon,
  SettingsIcon,
} from "@/components/ui";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Home", href: "/", icon: HomeIcon },
  { label: "Connectivity", href: "/connectivity", icon: ConnectivityIcon },
  { label: "Networks", href: "/networks", icon: NetworksIcon },
  { label: "Fulfillment", href: "/fulfillment", icon: FulfillmentIcon },
  { label: "Evidence", href: "/evidence", icon: EvidenceIcon },
  { label: "Developers", href: "/developers", icon: DevelopersIcon },
  { label: "Assurance", href: "/assurance", icon: AssuranceIcon },
  { label: "Settings", href: "/settings", icon: SettingsIcon },
];

function isNavItemActive(href: string, pathname: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar() {
  const pathname = usePathname() ?? "/";

  return (
    <nav
      aria-label="Primary"
      className="sticky top-0 z-10 flex h-screen w-14 shrink-0 flex-col border-r border-line bg-surface lg:w-56"
    >
      <ul className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2">
        {NAV_ITEMS.map((item) => {
          const active = isNavItemActive(item.href, pathname);
          const Icon = item.icon;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                title={item.label}
                aria-label={item.label}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center justify-center gap-2.5 rounded border-l-2 px-2 py-1.5 text-sm lg:justify-start lg:px-2.5",
                  active
                    ? "border-accent bg-raised text-ink"
                    : "border-transparent text-ink-muted hover:bg-raised/60 hover:text-ink",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="hidden lg:inline">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>

      <div className="border-t border-line p-2 font-mono text-2xs text-ink-faint lg:p-3">
        <p className="hidden lg:block">ADCOS console</p>
        <p className="hidden lg:block">developer API 2.0</p>
      </div>
    </nav>
  );
}
