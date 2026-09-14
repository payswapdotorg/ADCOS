"use client";

/**
 * The credential/session store — IN MEMORY ONLY (spec non-negotiable #9).
 *
 * The application id + credential live in React state; NOTHING is ever
 * written to localStorage/sessionStorage/cookies. A reload clears the
 * session by design. `connect` validates via the real boundary
 * (GET /api/2.0/application) before a session is accepted; `disconnect`
 * clears it. Every request flows through the typed client, which also
 * feeds the in-memory request log (features/requests).
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";
import { AdcosClient, type AdcosSession } from "@/lib/api/client";
import { AdcosApiError } from "@/lib/api/errors";
import type { Application } from "@/lib/api/types";
import { recordRequest } from "@/features/requests/request-log";

export type SessionStatus = "disconnected" | "connecting" | "connected";

interface SessionContextValue {
  status: SessionStatus;
  /** The connected application profile (null until connected). */
  application: Application | null;
  /** The last connect failure (typed; reason verbatim). */
  error: AdcosApiError | null;
  /** The shared client — usable unauthenticated for platform routes. */
  client: AdcosClient;
  /** Validate + store a session; resolves false on failure. */
  connect: (applicationId: string, credential: string) => Promise<boolean>;
  /** Clear the session (and the application profile). */
  disconnect: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AdcosSession | null>(null);
  const [application, setApplication] = useState<Application | null>(null);
  const [status, setStatus] = useState<SessionStatus>("disconnected");
  const [error, setError] = useState<AdcosApiError | null>(null);
  // serialize connects so double-submits cannot interleave
  const connecting = useRef(false);

  const client = useMemo(
    () =>
      new AdcosClient(session, {
        onRequest: recordRequest,
      }),
    [session],
  );

  const connect = useCallback(
    async (applicationId: string, credential: string): Promise<boolean> => {
      if (connecting.current) return false;
      connecting.current = true;
      setStatus("connecting");
      setError(null);
      try {
        const candidate = new AdcosClient(
          { applicationId, credential },
          { onRequest: recordRequest },
        );
        const envelope = await candidate.applicationSelf();
        setSession({ applicationId, credential });
        setApplication(envelope.data);
        setStatus("connected");
        return true;
      } catch (caught) {
        const typed =
          caught instanceof AdcosApiError
            ? caught
            : new AdcosApiError({
                status: 0,
                reason: "backend-unreachable",
                message: "The connect attempt failed before reaching the boundary",
                request: { method: "GET", path: "/api/2.0/application" },
              });
        setError(typed);
        setStatus("disconnected");
        return false;
      } finally {
        connecting.current = false;
      }
    },
    [],
  );

  const disconnect = useCallback(() => {
    setSession(null);
    setApplication(null);
    setStatus("disconnected");
    setError(null);
  }, []);

  const value = useMemo(
    () => ({ status, application, error, client, connect, disconnect }),
    [status, application, error, client, connect, disconnect],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used inside SessionProvider");
  }
  return context;
}
