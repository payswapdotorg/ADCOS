import type { Metadata } from "next";
import { AreaPlaceholder } from "@/components/shell/area-placeholder";

export const metadata: Metadata = {
  title: "Developers",
};

/**
 * Developers — placeholder surface for Worker 3.
 *
 * The frozen UX spec's developer map: applications, credentials,
 * capabilities, the API explorer (supported endpoints only) and the
 * request inspector.
 */
export default function DevelopersPage() {
  return (
    <AreaPlaceholder
      title="Developers"
      intro="This area is being implemented (Worker 3 — evidence, developers, assurance)."
      map={[
        {
          title: "Applications",
          description:
            "Identity, environment, credential state, capabilities, API version, recent activity.",
        },
        {
          title: "Credentials",
          description:
            "Issuance state, masked value/state, one-time reveal where supported, revoke/rotate where supported.",
        },
        {
          title: "Capabilities",
          description:
            "Effective grants and explanations for missing capability.",
        },
        {
          title: "API Explorer",
          description:
            "Supported endpoints only (method, path, headers, body/schema, response, status, canonical reason code, curl).",
        },
        {
          title: "Request Inspector",
          description:
            "Resource JSON and the API operation that produced it.",
        },
      ]}
    />
  );
}
