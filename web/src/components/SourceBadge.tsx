/**
 * Source badge: every figure carries its source (plan, principle 6).
 * Shows meta.source verbatim — mock, live, cache or fixture.
 */
import type { ReactElement } from "react";
import type { Source } from "../contract";

export function SourceBadge({ source }: { source: Source | null }): ReactElement {
  return (
    <span
      className="source-badge"
      data-testid="source-badge"
      data-source={source ?? "unknown"}
      title="Where the data behind this page came from"
    >
      source: {source ?? "…"}
    </span>
  );
}
