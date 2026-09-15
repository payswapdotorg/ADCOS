"use client";

/**
 * The primary navigation rail.
 *
 * Fixed-width (224px at `lg` and up, 56px icon-only below), one entry per
 * console area, active route marked with `aria-current="page"` and the
 * teal left border. The nav vocabulary matches the command registry's
 * "Navigate" group exactly — one mental model for mouse and keyboard.
 *
 * V2 learning surfaces include Docs, Build with ADCOS, Quickstart,
 * Playbooks and the tour. Expert routes remain direct and are never
 * replaced by an onboarding redirect.
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
  SearchIcon,
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

const LEARN_ITEMS: NavItem[] = [
  { label: "Docs", href: "/docs", icon: EvidenceIcon },
  { label: "Build with ADCOS", href: "/build", icon: ConnectivityIcon },
  { label: "Quickstart", href: "/quickstart", icon: FulfillmentIcon },
  { label: "Playbooks", href: "/playbooks", icon: SearchIcon },
  { label: "The tour", href: "/tour", icon: NetworksIcon },
];

function isNavItemActive(href: string, pathname: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavList({
  items,
  id,
  label,
  grow = true,
}: {
  items: NavItem[];
  id: string;
  label: string;
  grow?: boolean;
}) {
  const pathname = usePathname() ?? "/";
  return (
    <ul
      id={id}
      aria-label={label}
      className={cn(
        "flex flex-col gap-0.5 overflow-y-auto p-2",
        grow && "flex-1",
      )}
    >
      {items.map((item) => {
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
  );
}

export function Sidebar() {
  return (
    <nav
      aria-label="Primary"
      className="sticky top-0 z-10 flex h-screen w-14 shrink-0 flex-col border-r border-line bg-surface lg:w-56"
    >
      <NavList items={NAV_ITEMS} id="primary-nav-items" label="Primary areas" />

      <div className="border-t border-line px-2 py-1.5 lg:px-3">
        <p
          id="learn-nav-heading"
          className="hidden text-2xs uppercase tracking-wide text-ink-faint lg:block"
        >
          Learn & build
        </p>
      </div>
      <NavList items={LEARN_ITEMS} id="learn-nav-items" label="Learn and build" grow={false} />

      <div className="border-t border-line p-2 font-mono text-2xs text-ink-faint lg:p-3">
        <p className="hidden lg:block">ADCOS console</p>
        <p className="hidden lg:block">developer API 2.0</p>
      </div>
    </nav>
  );
}
