import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider, themeInitScript } from "@/lib/design/theme";
import { SessionProvider } from "@/lib/session";
import { AppShell } from "@/components/shell/app-shell";

export const metadata: Metadata = {
  title: {
    default: "ADCOS Developer Console",
    template: "%s · ADCOS",
  },
  description:
    "The developer control surface for the ADCOS programmable connectivity exchange.",
};

/**
 * The root layout: every console route renders inside the app shell.
 *
 * Provider order is fixed: theme (visual only) wraps the session (API
 * identity, in-memory ONLY — a reload clears the credential by design)
 * which wraps the shell (sidebar + top bar + main region).
 */
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        {/* apply the persisted (non-secret) theme preference pre-paint */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <ThemeProvider>
          <SessionProvider>
            <AppShell>{children}</AppShell>
          </SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
