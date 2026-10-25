// SPDX-License-Identifier: Apache-2.0
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { cents, formatCents } from "./money.ts";

// @req R-MONEY-CENTS
describe("money", () => {
  it("rejects fractions of a cent", () => {
    assert.equal(cents(1_205), 1_205);
    assert.throws(() => cents(12.5), RangeError);
  });

  it("formats dollars and cents", () => {
    assert.equal(formatCents(1_205), "12.05");
    assert.equal(formatCents(-310), "-3.10");
    assert.equal(formatCents(7), "0.07");
  });
});
