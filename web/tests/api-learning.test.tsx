/**
 * API-learning tests — the education the V2 API Explorer composes
 * around each operation (DEC-0128, Task 6) and the canonical
 * reason-code troubleshooting table (Task 7), at the
 * FEATURE-COMPONENT level: the REAL OperationDetail rendered with the
 * REAL intent_create coverage record, no network, no session (the
 * detail takes its session facts as props).
 *
 * Covers the work order's demands:
 * - the operation detail renders the "About this operation" education
 *   affordance, COLLAPSED by default (the V1 expert density preserved —
 *   the registry education is not in the DOM until opted into);
 * - expanding shows the REAL registry purpose, prerequisites, lifecycle
 *   position, typical sequence and fieldExplanations of a real
 *   operation (intent_create);
 * - the related reason codes link to their /docs/errors#code-<code>
 *   anchors; the next operation links to the next operation's detail in
 *   the Explorer;
 * - the request-language example is a curl derived ONLY from the
 *   operation's own registry metadata, with the credential masked;
 * - the V1 execution surfaces keep rendering exactly as before (the
 *   zero-regression companion to tests/api-explorer.test.tsx);
 * - the reason-guidance table covers exactly the canonical vocabulary
 *   (32 codes, the docs Errors page's pin) and unknown codes resolve to
 *   NO guidance (never invented semantics).
 */

import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { coverageByOperation } from "@/lib/api/coverage";
import { getOperationEducation } from "@/lib/education";
import { PINNED_REASON_CODES } from "@/features/docs";
import { OperationDetail } from "@/features/api-explorer/operation-detail";
import {
  OPERATION_EDUCATION_TEST_IDS,
  OperationEducationPanel,
  REASON_TROUBLESHOOTING,
  getReasonTroubleshooting,
  isCanonicalReasonCode,
  reasonTroubleshootingForCodes,
} from "@/features/api-learning";

/* ------------------------------------------------------------------ *
 * The OperationDetail education integration
 * ------------------------------------------------------------------ */

function renderIntentCreateDetail() {
  const record = coverageByOperation("intent_create");
  if (!record) throw new Error("intent_create is not in the coverage registry");
  const education = getOperationEducation("intent_create");
  if (!education) throw new Error("intent_create has no education record");

  render(
    <OperationDetail
      record={record}
      connected={false}
      applicationId={null}
      capabilities={null}
      pathParams={{}}
      onPathParamChange={() => undefined}
      bodyText={JSON.stringify(record.example ?? {}, null, 2)}
      onBodyTextChange={() => undefined}
      bodyEditable
      idempotencyKey=""
      onIdempotencyKeyChange={() => undefined}
      confirming={false}
      onRequestExecute={() => undefined}
      onConfirmExecute={() => undefined}
      onCancelConfirm={() => undefined}
      running={false}
      invalidMessage={null}
    />,
  );
  return { record, education };
}

describe("OperationDetail — the V2 education affordance", () => {
  it("renders the collapsed-by-default 'About this operation' affordance (nothing else changes)", () => {
    const { record } = renderIntentCreateDetail();

    // the affordance exists and is collapsed (aria-expanded disclosure)
    const trigger = screen.getByTestId(OPERATION_EDUCATION_TEST_IDS.trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveAccessibleName(/About this operation/);

    // COLLAPSED means absent: no panel, no registry education strings
    expect(screen.queryByTestId(OPERATION_EDUCATION_TEST_IDS.panel)).toBeNull();
    expect(
      screen.queryByText(
        "Record a connectivity intent — the contract creation core. The principal is derived from the authenticated application.",
      ),
    ).toBeNull();
    expect(screen.queryByText(/Immutable after creation/)).toBeNull();

    // the V1 execution surfaces render EXACTLY as before
    expect(screen.getByText(record.description)).toBeInTheDocument();
    expect(screen.getByText("Request headers")).toBeInTheDocument();
    expect(screen.getByText("<your-application-id>")).toBeInTheDocument();
    expect(screen.getByText("<your-credential>")).toBeInTheDocument();
    expect(
      (screen.getByLabelText("Request body JSON") as HTMLTextAreaElement).value,
    ).toContain("demo:intent-requirements:v1");
    expect(screen.getByLabelText("Idempotency key")).toBeInTheDocument();
    expect(
      screen.getByText("Connect an application to execute authenticated developer-API operations."),
    ).toBeInTheDocument();
    expect(screen.getByTestId("execute-operation")).toBeDisabled();
  });

  it("expanding shows the REAL registry education of intent_create (purpose, fields, curl, links)", () => {
    const { record, education } = renderIntentCreateDetail();

    fireEvent.click(screen.getByTestId(OPERATION_EDUCATION_TEST_IDS.trigger));

    // the disclosure opened
    expect(screen.getByTestId(OPERATION_EDUCATION_TEST_IDS.trigger)).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    const panel = screen.getByTestId(OPERATION_EDUCATION_TEST_IDS.panel);

    // the REAL registry purpose / prerequisites / lifecycle / sequence
    expect(within(panel).getByText(education.purpose)).toBeInTheDocument();
    expect(within(panel).getByText(education.prerequisites)).toBeInTheDocument();
    expect(within(panel).getByText(education.lifecyclePosition)).toBeInTheDocument();
    expect(within(panel).getByText(education.typicalSequence)).toBeInTheDocument();

    // the REAL field explanations (the mutation's example body fields)
    for (const field of education.fieldExplanations) {
      expect(within(panel).getByText(field.field)).toBeInTheDocument();
    }
    expect(
      within(panel).getByText(/Immutable after creation; a replan re-verifies against them/),
    ).toBeInTheDocument();

    // the curl example derives ONLY from the operation's own metadata:
    // the registry method, path template, example body and masked headers
    const curlCode = Array.from(panel.querySelectorAll("code")).find((element) =>
      element.textContent?.includes(`curl -X POST '${record.path}'`),
    );
    expect(curlCode).toBeDefined();
    expect(curlCode?.textContent).toContain("X-ADCOS-Credential: <your-credential>");
    expect(curlCode?.textContent).toContain("X-ADCOS-Application: <your-application-id>");
    expect(curlCode?.textContent).toContain(
      "X-ADCOS-Idempotency-Key: <fresh-idempotency-key>",
    );
    expect(curlCode?.textContent).toContain("demo:intent-requirements:v1");
    // NO invented language SDK examples anywhere in the panel
    expect(panel.textContent).not.toMatch(/pip install|npm install|go get|gem install/);

    // the related concepts render as the W1 drawer chips
    expect(
      within(panel).getByRole("button", { name: /What is: Connectivity contract/ }),
    ).toBeInTheDocument();

    // the related reason codes link to their docs anchors, VERBATIM ids
    for (const code of education.relatedErrors) {
      const link = within(panel).getByRole("link", { name: code });
      expect(link).toHaveAttribute("href", `/docs/errors#code-${code}`);
    }

    // the next operation links to the next operation's detail in the Explorer
    const nextLink = within(panel).getByRole("link", { name: education.nextOperation ?? "" });
    expect(nextLink).toHaveAttribute(
      "href",
      `/developers/explorer?operation=${education.nextOperation}`,
    );
    expect(nextLink.textContent).toBe(education.nextOperation);
  });
});

/* ------------------------------------------------------------------ *
 * The standalone panel (other compositions)
 * ------------------------------------------------------------------ */

describe("OperationEducationPanel — the standalone education block", () => {
  it("renders honest nothing for an operation without an education record", () => {
    const { container } = render(
      <OperationEducationPanel
        record={{
          operation: "not_a_registry_operation",
          method: "GET",
          path: "/nowhere",
          mutation: false,
          requiredCapability: "",
          platform: false,
          uiLocation: "",
          description: "",
        }}
        applicationId={null}
      />,
    );
    expect(container.textContent).toBe("");
  });

  it("renders a bodyless read's honest no-body education without a curl body", () => {
    const record = coverageByOperation("healthz");
    if (!record) throw new Error("healthz is not in the coverage registry");

    const { container } = render(
      <OperationEducationPanel record={record} applicationId="sha256:app" />,
    );
    const trigger = screen.getByTestId(OPERATION_EDUCATION_TEST_IDS.trigger);
    fireEvent.click(trigger);

    // the bodyless GET's honest field explanation renders
    expect(container.textContent).toContain(
      "None — a bodyless GET. The response is the liveness document",
    );
    // no mutation → no idempotency header in the derived curl
    const curlCode = Array.from(container.querySelectorAll("code")).find((element) =>
      element.textContent?.includes("curl -X GET '/healthz'"),
    );
    expect(curlCode).toBeDefined();
    expect(curlCode?.textContent).not.toContain("Idempotency");
    // the platform surface carries no auth headers at all
    expect(curlCode?.textContent).not.toContain("X-ADCOS-Credential");
  });
});

/* ------------------------------------------------------------------ *
 * The reason-guidance data contract
 * ------------------------------------------------------------------ */

describe("reason-guidance — the canonical troubleshooting table", () => {
  it("covers EXACTLY the canonical reason-code vocabulary (the docs Errors pin), no duplicates", () => {
    expect(REASON_TROUBLESHOOTING).toHaveLength(32);
    expect(PINNED_REASON_CODES).toHaveLength(32);

    const table = REASON_TROUBLESHOOTING.map((entry) => entry.code).sort();
    const pin = [...PINNED_REASON_CODES].sort();
    expect(table).toEqual(pin);

    for (const entry of REASON_TROUBLESHOOTING) {
      expect(isCanonicalReasonCode(entry.code)).toBe(true);
      // the six-part anatomy is fully written for every canonical code
      expect(entry.whatHappened.length).toBeGreaterThan(10);
      expect(entry.why.length).toBeGreaterThan(10);
      expect(entry.affectedResource.length).toBeGreaterThan(10);
      expect(entry.nextAction.length).toBeGreaterThan(10);
      expect(entry.apiReproduction.length).toBeGreaterThan(10);
    }
  });

  it("resolves the captured error's own codes and stays undefined for unknown codes", () => {
    // the boundary reason first
    expect(reasonTroubleshootingForCodes("resource-unknown", "unknown-contract")?.code).toBe(
      "resource-unknown",
    );
    // a non-canonical boundary reason falls back to the adapted canonical code
    expect(reasonTroubleshootingForCodes("some-frontend-code", "unknown-contract")?.code).toBe(
      "unknown-contract",
    );
    // unknown codes resolve to NO guidance — never invented semantics
    expect(reasonTroubleshootingForCodes("mystery-code", null)).toBeUndefined();
    expect(reasonTroubleshootingForCodes("mystery-code", "also-mystery")).toBeUndefined();
    expect(getReasonTroubleshooting("mystery-code")).toBeUndefined();
    expect(isCanonicalReasonCode("mystery-code")).toBe(false);
  });
});
