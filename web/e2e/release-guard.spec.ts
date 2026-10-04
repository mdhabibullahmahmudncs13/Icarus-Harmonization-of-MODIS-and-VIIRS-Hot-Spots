import { spawnSync } from "node:child_process";
import { expect, test } from "@playwright/test";

/**
 * Release guard (plan, principle 3): a release build refuses to start in
 * mock mode. VITE_DATA defaults to mock, so unset must fail too.
 */

const webDir = decodeURIComponent(new URL("..", import.meta.url).pathname);

function runBuildRelease(viteData: string | undefined): { status: number | null; output: string } {
  const env = { ...process.env };
  if (viteData === undefined) delete env.VITE_DATA;
  else env.VITE_DATA = viteData;
  const res = spawnSync("npm", ["run", "build:release"], {
    cwd: webDir,
    env,
    encoding: "utf8",
  });
  return { status: res.status, output: `${res.stdout ?? ""}${res.stderr ?? ""}` };
}

test("build:release fails with VITE_DATA=mock", () => {
  const { status, output } = runBuildRelease("mock");
  expect(status).not.toBe(0);
  expect(output).toContain("release-guard");
  expect(output).toContain("refusing to build");
});

test("build:release fails when VITE_DATA is unset (default is mock)", () => {
  const { status, output } = runBuildRelease(undefined);
  expect(status).not.toBe(0);
  expect(output).toContain("release-guard");
});
