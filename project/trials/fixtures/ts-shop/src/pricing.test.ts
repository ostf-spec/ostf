// SPDX-License-Identifier: Apache-2.0
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { applyDiscount, DiscountExpiredError, price, tax, type Region } from "./pricing.ts";

const now = new Date("2026-03-01T12:00:00Z");
const later = new Date("2026-03-02T12:00:00Z");
const quebec: Region = { code: "QC", ratePpm: 149_750 };

describe("applyDiscount", () => {
  it("takes the percentage off", () => {
    assert.equal(applyDiscount(10_000, { code: "TEN", percent: 10, expires: later }, now), 1_000);
  });

  it("rounds down to the cent", () => {
    assert.equal(applyDiscount(999, { code: "FIFTEEN", percent: 15, expires: later }, now), 149);
  });

  it("caps at fifty percent", () => {
    assert.equal(applyDiscount(10_000, { code: "TYPO", percent: 100, expires: later }, now), 5_000);
  });

  it("rejects an expired code", () => {
    assert.throws(() => applyDiscount(10_000, { code: "OLD", percent: 10, expires: now }, now), DiscountExpiredError);
  });
});

describe("tax", () => {
  it("rounds half up to the cent", () => {
    assert.equal(tax(10_000, quebec, false), 1_498);
    assert.equal(tax(100, quebec, false), 15);
    assert.equal(tax(0, quebec, false), 0);
  });

  // @req R-TAX-EXEMPT
  it("is zero for a tax-exempt customer", () => {
    assert.equal(tax(10_000, quebec, true), 0);
  });
});

describe("price", () => {
  it("taxes the subtotal after discounts", () => {
    const quote = price(10_000, { code: "TEN", percent: 10, expires: later }, quebec, false, now);
    assert.deepEqual(quote, { subtotal: 10_000, discount: 1_000, tax: 1_348, total: 10_348 });
  });
});
