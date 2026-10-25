// SPDX-License-Identifier: Apache-2.0
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { HOLD_MS, InsufficientStockError, NoReservationError, Stock } from "./inventory.ts";

function newStock(): { stock: Stock; clock: { t: number } } {
  const clock = { t: Date.parse("2026-03-01T12:00:00Z") };
  const stock = new Stock(() => new Date(clock.t));
  stock.receive("mug", 3);
  stock.receive("tea", 1);
  return { stock, clock };
}

describe("Stock", () => {
  // @req R-STOCK-RESERVE
  it("reserves all lines or none", () => {
    const { stock } = newStock();
    assert.throws(() => stock.reserve(new Map([["mug", 2], ["tea", 2]])), InsufficientStockError);
    assert.equal(stock.available("mug"), 3);
    stock.reserve(new Map([["mug", 2], ["tea", 1]]));
    assert.equal(stock.available("mug"), 1);
  });

  it("releases a reservation", () => {
    const { stock } = newStock();
    const hold = stock.reserve(new Map([["mug", 3]]));
    stock.release(hold.id);
    assert.equal(stock.available("mug"), 3);
  });

  // @req R-STOCK-EXPIRY
  it("expires a reservation after 15 minutes", () => {
    const { stock, clock } = newStock();
    const hold = stock.reserve(new Map([["mug", 3]]));
    clock.t += HOLD_MS;
    assert.equal(stock.available("mug"), 3);
    assert.throws(() => stock.confirm(hold.id), NoReservationError);
  });

  it("confirms a reservation as a sale", () => {
    const { stock } = newStock();
    const hold = stock.reserve(new Map([["mug", 2]]));
    stock.confirm(hold.id);
    assert.equal(stock.available("mug"), 1);
    assert.throws(() => stock.confirm(hold.id), NoReservationError);
  });
});
