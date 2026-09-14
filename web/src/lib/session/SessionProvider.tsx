"use client";

/**
 * The credential/session store (charter §4.4).
 *
 * NON-NEGOTIABLE #9: the application credential lives IN MEMORY ONLY —
 * a React context, never localStorage/sessionStorage/cookies. A reload
 * clears the session BY DESIGN; production users re-enter their issued
 * credentials. The theme preference (lib/design/use-theme.ts) is the
 * ONLY thing this console persists, and it is not a secret.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createAdcosClient, type AdcosClient, type AdcosSession } from "@/lib/api/client";
import type { Application } from "@/lib/api/types";

/** The connected session: credentials + the validated application self view. */
export interface ConnectedSession extends AdcosSession {
  application: Application;
}

export interface SessionContextValue {
  /** The connected session or null (public operations still work). */
  session: ConnectedSession | null;
  /** The typed client bound to the current session (public client when null). */
  client: AdcosClient;
  /** Validate credentials via applicationSelf and connect (in memory). */
  connect: (applicationId: string, credential: string) => Promise<Application>;
  /** Clear the session (memory only — there is nothing else to clear). */
  disconnect: () => void;
  connecting: boolean;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<ConnectedSession | null>(null);
  const [connecting, setConnecting] = useState(false);

  const publicClient = useMemo(() => createAdcosClient(null), []);

  const client = useMemo(
    () =>
      session
        ? createAdcosClient({
            applicationId: session.applicationId,
            credential: session.credential,
          })
        : publicClient,
    [session, publicClient],
  );

  const connect = useCallback(
    async (applicationId: string, credential: string): Promise<Application> => {
      setConnecting(true);
      try {
        // Validate through the boundary itself — the console never
        // decides locally whether credentials are good.
        const candidate = createAdcosClient({ applicationId, credential });
        const result = await candidate.applicationSelf();
        const connected: ConnectedSession = {
          applicationId,
          credential,
          application: result.data,
        };
        setSession(connected);
        return result.data;
      } finally {
        setConnecting(false);
      }
    },
    [],
  );

  const disconnect = useCallback(() => setSession(null), []);

  const value = useMemo<SessionContextValue>(
    () => ({ session, client, connect, disconnect, connecting }),
    [session, client, connect, disconnect, connecting],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("useSession requires <SessionProvider> (the shell provides it)");
  }
  return value;
}
