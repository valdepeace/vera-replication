import assert from "node:assert/strict";
import { test } from "node:test";
import { bestByRound, nodeDir } from "./treeModel.ts";

test("nodeDir baseline", () => {
  assert.equal(nodeDir("iter000", 1, 0), "history/iter000/explore_b1/attempt_00");
});

test("bestByRound baseline", () => {
  const run = { rounds: [{ trace: { nodes: [{ raw: { evaluated: true, combinedScore: 0.9 } }] } }] };
  assert.deepEqual(bestByRound(run as any), [0.9]);
});
