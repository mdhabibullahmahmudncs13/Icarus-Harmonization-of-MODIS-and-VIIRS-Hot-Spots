/**
 * Mode state and URL sync tests.
 * The URL query string is the source of truth for mode and selected date.
 */
import { beforeEach, describe, expect, it } from "vitest";
import {
  DEFAULT_STATE,
  parseAppState,
  parseMode,
  serializeAppState,
  writeStateToUrl,
} from "../../src/state/urlState";

describe("parseMode", () => {
  it("accepts both modes", () => {
    expect(parseMode("raw")).toBe("raw");
    expect(parseMode("harmonized")).toBe("harmonized");
  });

  it("falls back to raw for anything else", () => {
    expect(parseMode(null)).toBe("raw");
    expect(parseMode(undefined)).toBe("raw");
    expect(parseMode("")).toBe("raw");
    expect(parseMode("RAW")).toBe("raw");
    expect(parseMode("bogus")).toBe("raw");
  });
});

describe("parseAppState", () => {
  it("defaults to raw with no date", () => {
    expect(parseAppState("")).toEqual(DEFAULT_STATE);
    expect(parseAppState("?")).toEqual({ mode: "raw", date: null });
  });

  it("reads mode from the query string", () => {
    expect(parseAppState("?mode=harmonized")).toEqual({ mode: "harmonized", date: null });
    expect(parseAppState("?mode=raw")).toEqual({ mode: "raw", date: null });
  });

  it("reads a valid date and rejects an invalid one", () => {
    expect(parseAppState("?date=2012-03-01").date).toBe("2012-03-01");
    expect(parseAppState("?date=not-a-date").date).toBeNull();
    expect(parseAppState("?date=2012-3-1").date).toBeNull();
  });

  it("reads mode and date together", () => {
    expect(parseAppState("?mode=harmonized&date=2024-03-15")).toEqual({
      mode: "harmonized",
      date: "2024-03-15",
    });
  });
});

describe("serializeAppState", () => {
  it("always includes mode", () => {
    expect(serializeAppState({ mode: "raw", date: null })).toBe("?mode=raw");
    expect(serializeAppState({ mode: "harmonized", date: null })).toBe("?mode=harmonized");
  });

  it("includes date only when set", () => {
    expect(serializeAppState({ mode: "raw", date: "2012-01-01" })).toBe(
      "?mode=raw&date=2012-01-01",
    );
  });

  it("round-trips through parseAppState", () => {
    for (const state of [
      { mode: "raw" as const, date: null },
      { mode: "harmonized" as const, date: null },
      { mode: "harmonized" as const, date: "2020-02-29" },
    ]) {
      expect(parseAppState(serializeAppState(state))).toEqual(state);
    }
  });
});

describe("URL sync", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("writeStateToUrl puts state in location.search and parseAppState reads it back", () => {
    const state = { mode: "harmonized" as const, date: "2012-03-01" };
    writeStateToUrl(state);
    expect(window.location.search).toBe("?mode=harmonized&date=2012-03-01");
    expect(parseAppState(window.location.search)).toEqual(state);
  });

  it("mode changes round-trip through history", () => {
    writeStateToUrl({ mode: "raw", date: null });
    expect(parseAppState(window.location.search).mode).toBe("raw");
    writeStateToUrl({ mode: "harmonized", date: null });
    expect(parseAppState(window.location.search).mode).toBe("harmonized");
  });
});
