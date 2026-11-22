import assert from "node:assert/strict";
import { test } from "node:test";
import { chunkText, normalizeWhitespace } from "./targets.mjs";

test("fixture baseline", () => {
  assert.equal(normalizeWhitespace("  a   b\n"), "a b");
  assert.deepEqual(chunkText("abcd", 2), ["ab", "cd"]);
});
