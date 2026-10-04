/**
 * Persistent banner while the app runs on mock data.
 * Mock data is never evidence (plan, principle 3): no number from mock
 * mode goes into the video, the project page or the methods panel.
 */
import type { ReactElement } from "react";
import type { Source } from "../contract";

export function MockBanner({ source }: { source: Source | null }): ReactElement | null {
  if (source !== "mock") return null;
  return (
    <div className="mock-banner" role="status" data-testid="mock-banner">
      <strong>Mock data.</strong> These numbers are generated for the demo and are not evidence.
      Nothing here may be used in the video, project page or methods panel.
    </div>
  );
}
