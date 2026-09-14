import type { Metadata } from "next";
import { HomeView } from "@/features/home";

export const metadata: Metadata = {
  title: "Home",
};

/**
 * Home — the dashboard that answers immediately: is ADCOS healthy, what
 * connectivity is managed, what is changing, what needs attention (plan
 * Task 4). Thin server file; the interactive view is the client feature.
 */
export default function HomePage() {
  return <HomeView />;
}
