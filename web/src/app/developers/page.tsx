import type { Metadata } from "next";
import { DevelopersWorkspace } from "@/features/developers";

export const metadata: Metadata = {
  title: "Developers",
};

/**
 * Developers — the developer workspace (station A, the
 * console-developers core): the connected application's identity,
 * capabilities and credential state, plus the webhook endpoints
 * surface. The workspace is a client component (session-aware); this
 * route stays a thin server wrapper.
 */
export default function DevelopersPage() {
  return <DevelopersWorkspace />;
}
