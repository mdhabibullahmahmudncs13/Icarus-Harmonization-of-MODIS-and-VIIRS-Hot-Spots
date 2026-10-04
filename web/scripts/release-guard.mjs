// Release build guard.
// A release build must never ship with mock data (Implementation plan, principle 3:
// "Mock data is never evidence. A release build refuses to start in mock mode.").
// VITE_DATA defaults to "mock" in the app, so an unset value counts as mock here too.
const source = process.env.VITE_DATA ?? "mock";

if (source === "mock") {
  console.error(
    `\nrelease-guard: refusing to build.\n` +
      `  VITE_DATA=${JSON.stringify(source)}${process.env.VITE_DATA === undefined ? " (unset, default is mock)" : ""}\n` +
      `  Mock data is never evidence. Set VITE_DATA=api (or cache/fixture once implemented)\n` +
      `  to produce a release build.\n`,
  );
  process.exit(1);
}

console.log(`release-guard: VITE_DATA=${source}, ok.`);
