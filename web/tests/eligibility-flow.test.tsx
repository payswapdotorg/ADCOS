/**
 * Eligibility / policy presentation tests — the shared Worker 2
 * presentation layer against REAL captured lifecycle shapes:
 *
 * - the flow-state panel renders the backend's own statements VERBATIM
 *   (contract_state, evidence_class "sandbox-simulation", note, statements);
 * - typed references render with provenance visible;
 * - useAdcosRead re-fetches on refresh (no cache authority) and surfaces
 *   typed errors with the verbatim reason.
 */

import { describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import {
  FlowStatePanel,
  RefList,
  RefValue,
  VerbatimNote,
  useAdcosRead,
  type AdcosReadState,
} from "@/features/eligibility";
import { useSession } from "@/lib/session";
import {
  FIXTURE_LIFECYCLE_INTENT,
  FIXTURE_USAGE,
} from "./fixtures";
import {
  APPLICATION_ROUTE,
  envelope,
  renderWithSession,
  routeFetch,
} from "./harness";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useParams: () => ({}),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: Record<string, unknown>) => (
    <a href={href as string} {...props}>
      {children as never}
    </a>
  ),
}));

describe("VerbatimNote", () => {
  it("renders the backend note text EXACTLY as captured", () => {
    render(<VerbatimNote note={FIXTURE_USAGE.note} />);
    expect(screen.getByTestId("verbatim-note")).toHaveTextContent(
      FIXTURE_USAGE.note,
    );
    expect(screen.getByText("(verbatim)")).toBeInTheDocument();
  });
});

describe("RefValue / RefList", () => {
  it("renders the typed reference with ref_kind, value and provenance", () => {
    render(<RefValue reference={FIXTURE_LIFECYCLE_INTENT.assurance_obligation_refs[0]} />);
    expect(screen.getByText("assurance-obligation")).toBeInTheDocument();
    expect(screen.getByText("capture:assurance:v1")).toBeInTheDocument();
    expect(screen.getByText(/issuer assurance-authority/)).toBeInTheDocument();
    expect(screen.getByText(/decision_refs capture:assurance:v1/)).toBeInTheDocument();
  });

  it("renders the honest empty label when no references exist", () => {
    render(<RefList references={[]} emptyLabel="none recorded" />);
    expect(screen.getByText("none recorded")).toBeInTheDocument();
  });
});

describe("FlowStatePanel", () => {
  it("renders the lifecycle's own explanation verbatim", () => {
    render(<FlowStatePanel lifecycle={FIXTURE_LIFECYCLE_INTENT} />);
    // the state, verbatim backend vocabulary
    expect(screen.getByText("INTENT")).toBeInTheDocument();
    // the evidence class, verbatim + visibly software-side
    expect(screen.getAllByText("sandbox-simulation").length).toBeGreaterThan(0);
    // the note, verbatim
    expect(screen.getByTestId("verbatim-note")).toHaveTextContent(
      FIXTURE_LIFECYCLE_INTENT.note,
    );
    // the statements vocabulary
    expect(screen.getByText("api_request_accepted")).toBeInTheDocument();
    expect(screen.getByText("physical_connectivity_not_claimed")).toBeInTheDocument();
    // the execution + physical position members
    expect(screen.getByText("not-started")).toBeInTheDocument();
    expect(screen.getByText("not-claimed")).toBeInTheDocument();
    expect(screen.getByText("false")).toBeInTheDocument();
  });
});

describe("useAdcosRead", () => {
  it("fetches through the session client and refresh re-fetches (no cache)", async () => {
    let reads = 0;
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /api/2.0/contracts/sha256:test-contract": () => {
        reads += 1;
        return envelope({ ok: true, read: reads });
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    // the hook reads through useSession()'s client: the probe surfaces it
    const state: { hook: AdcosReadState<{ ok: boolean; read: number }> | null } = {
      hook: null,
    };
    function ClientProbe() {
      const { client } = useSession();
      state.hook = useAdcosRead<{ ok: boolean; read: number }>(
        // the envelope fixture here is a synthetic probe payload — the
        // route is harnessed, so cast through unknown
        () =>
          client.getContract("sha256:test-contract") as unknown as Promise<{
            ok: boolean;
            read: number;
          }>,
        [],
      );
      return null;
    }

    // renderWithSession connects for real; the probe then reads
    renderWithSession(<ClientProbe />, fetchMock);

    await waitFor(() => {
      expect(state.hook?.loaded).toBe(true);
    });
    // the client resolves the canonical envelope; the hook stores it as-is
    expect(state.hook?.data).toEqual(envelope({ ok: true, read: 1 }));
    expect(state.hook?.error).toBeNull();

    await act(async () => {
      state.hook?.refresh();
    });
    await waitFor(() => {
      expect(state.hook?.data).toEqual(envelope({ ok: true, read: 2 }));
    });
    expect(reads).toBe(2);
    vi.unstubAllGlobals();
  });
});
