/**
 * Hand-drawn 16×16 stroke icons for the ADCOS console.
 *
 * NOT an icon library: every glyph is authored here for this design
 * language — simple geometry that stays legible at 16px with a 1.5px
 * stroke. Every icon inherits `currentColor`, is hidden from AT
 * (`aria-hidden`) and cannot take focus (`focusable="false"`); buttons
 * that render icons supply their own accessible name.
 */

import type { ReactNode } from "react";

export interface IconProps {
  /** Square render size in px (default 16). */
  size?: number;
  className?: string;
}

function Svg({
  size = 16,
  className,
  children,
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {children}
    </svg>
  );
}

/** The workbench home / overview. */
export function HomeIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M2.75 8.5 8 3.25l5.25 5.25" />
      <path d="M4.75 7.25v5.5h6.5v-5.5" />
    </Svg>
  );
}

/** Backend connectivity — a plug: prongs, body, cord. */
export function ConnectivityIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6.25 2.5v2M9.75 2.5v2" />
      <rect x="5" y="4.5" width="6" height="5" rx="1" />
      <path d="M8 9.5v4" />
    </Svg>
  );
}

/** Networks — three connected nodes. */
export function NetworksIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4.2 10.4 6.8 5.6M11.8 10.4 9.2 5.6M4.75 12.5h6.5" />
      <circle cx="8" cy="3.5" r="1.75" />
      <circle cx="3" cy="12.5" r="1.75" />
      <circle cx="13" cy="12.5" r="1.75" />
    </Svg>
  );
}

/** Fulfillment — flow from a source into an arrow. */
export function FulfillmentIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="3" cy="8" r="1.75" />
      <path d="M6.5 8h7" />
      <path d="M11 5.5 13.5 8 11 10.5" />
    </Svg>
  );
}

/** Evidence — a document carrying a verification badge. */
export function EvidenceIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4.25 2.25h4.75l3 2.75v8.75H4.25z" />
      <path d="M9 2.25v2.75h3" />
      <circle cx="10.75" cy="10.75" r="2.75" />
      <path d="M9.6 10.8l.8.8 1.5-1.7" />
    </Svg>
  );
}

/** Developers — code brackets. */
export function DevelopersIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5.25 4.5 2.25 8l3 3.5" />
      <path d="M10.75 4.5l3 3.5-3 3.5" />
      <path d="M8.75 3.5 7.25 12.5" />
    </Svg>
  );
}

/** Assurance — a shield with a check. */
export function AssuranceIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M8 2l4.5 1.6v3.3c0 3.1-1.8 5.4-4.5 6.5-2.7-1.1-4.5-3.4-4.5-6.5V3.6L8 2z" />
      <path d="M6.1 7.9l1.4 1.4 2.6-3" />
    </Svg>
  );
}

/** Settings — three sliders with knobs. */
export function SettingsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M2 4.25h6.5M11.5 4.25H14" />
      <circle cx="10" cy="4.25" r="1.5" />
      <path d="M2 8h2M7 8h7" />
      <circle cx="5.5" cy="8" r="1.5" />
      <path d="M2 11.75h5M10 11.75H14" />
      <circle cx="8.5" cy="11.75" r="1.5" />
    </Svg>
  );
}

/** Search — magnifier. */
export function SearchIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="7" cy="7" r="4.25" />
      <path d="M10.2 10.2 13.5 13.5" />
    </Svg>
  );
}

/** Copy — two overlapping sheets. */
export function CopyIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M10.5 2.5H3.75A1.25 1.25 0 0 0 2.5 3.75V10.5" />
      <rect x="5.5" y="5.5" width="8" height="8" rx="1.25" />
    </Svg>
  );
}

/** Check. */
export function CheckIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 8.75l3.25 3.25L13 4.75" />
    </Svg>
  );
}

/** Close / dismiss. */
export function CloseIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 4l8 8M12 4l-8 8" />
    </Svg>
  );
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 6.25 8 10.25l4-4" />
    </Svg>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6.25 4 10.25 8l-4 4" />
    </Svg>
  );
}

export function ChevronUpIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 9.75 8 5.75l4 4" />
    </Svg>
  );
}

/** Refresh — circular arrow. */
export function RefreshIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M14 8a6 6 0 1 1-6-6c1.68 0 3.29.67 4.49 1.83L14 5.33" />
      <path d="M14 2v3.33h-3.33" />
    </Svg>
  );
}

/** Alert — warning triangle. */
export function AlertIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M8 2.5 14.5 13.25h-13L8 2.5z" />
      <path d="M8 6.5v3.25" />
      <path d="M8 12.25h.01" />
    </Svg>
  );
}

/** Terminal — prompt box with chevron and cursor. */
export function TerminalIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="2" y="3" width="12" height="10" rx="1.5" />
      <path d="M4.75 6.5 6.5 8.25 4.75 10" />
      <path d="M9 10.25h2.5" />
    </Svg>
  );
}

/** Shield — plain (AssuranceIcon adds the check). */
export function ShieldIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M8 1.75 13 3.5v3.6c0 3.4-2.1 5.9-5 6.9-2.9-1-5-3.5-5-6.9V3.5L8 1.75z" />
    </Svg>
  );
}

/** Command — the ⌘ glyph (palette hotkey affordance). */
export function CommandIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 6V4a2 2 0 1 0-2 2h2" />
      <path d="M10 6V4a2 2 0 1 1 2 2h-2" />
      <path d="M10 10v2a2 2 0 1 0 2-2h-2" />
      <path d="M6 10v2a2 2 0 1 1-2-2h2" />
      <path d="M6 6h4v4H6z" />
    </Svg>
  );
}

/** External link — box with an escaping arrow. */
export function ExternalLinkIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6.5 3.25h-2A1.75 1.75 0 0 0 2.75 5v7.25A1.75 1.75 0 0 0 4.5 14h7.25a1.75 1.75 0 0 0 1.75-1.75v-2" />
      <path d="M9.5 3.25h3.75V7" />
      <path d="M13.25 3.25l-6.5 6.5" />
    </Svg>
  );
}

/** Inbox — empty-state tray. */
export function InboxIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M2.5 12.25V8.5l1.7-4.55A1.5 1.5 0 0 1 5.6 3h4.8a1.5 1.5 0 0 1 1.4.95l1.7 4.55v3.75a1.5 1.5 0 0 1-1.5 1.5h-8a1.5 1.5 0 0 1-1.5-1.5z" />
      <path d="M2.5 8.5h3.25l1 1.5h2.5l1-1.5h3.25" />
    </Svg>
  );
}
