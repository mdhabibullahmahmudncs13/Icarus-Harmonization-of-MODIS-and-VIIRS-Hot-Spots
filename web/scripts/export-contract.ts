/**
 * `npm run contract:export`
 *
 * Exports the zod contract to docs/contract.schema.json as JSON Schema
 * (draft-07), so the Python contract tests (pytest) can validate API
 * responses against the exact same source of truth the frontend uses.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { endpoints } from "../src/contract/schemas";

const here = dirname(fileURLToPath(import.meta.url));
const outPath = resolve(here, "../../docs/contract.schema.json");

const definitions = Object.fromEntries(
  Object.entries(endpoints).map(([name, schema]) => [
    name,
    z.toJSONSchema(schema, { target: "draft-7" }),
  ]),
);

const doc = {
  $schema: "http://json-schema.org/draft-07/schema#",
  title: "Icarus API responses",
  description:
    "JSON Schema (draft-07) for every Icarus API response. Generated from " +
    "web/src/contract/schemas.ts by `npm run contract:export`. One definition " +
    "per endpoint under `definitions`; validate a response body against " +
    "definitions.<endpoint>.",
  definitions,
};

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, JSON.stringify(doc, null, 2) + "\n", "utf8");
console.log(`contract:export wrote ${outPath} (${Object.keys(definitions).join(", ")})`);
