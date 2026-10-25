// SPDX-License-Identifier: Apache-2.0
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { Cart, QuantityError } from "./cart.ts";

describe("Cart", () => {
  // @req R-CART-ADD
  it("adds an item", () => {
    const cart = new Cart();
    cart.add("mug", 1_200, 1);
    cart.add("mug", 1_200, 2);
    assert.deepEqual(cart.lines(), [{ sku: "mug", unitPrice: 1_200, quantity: 3 }]);
  });

  it("rejects a quantity outside 1 to 99", () => {
    const cart = new Cart();
    assert.throws(() => cart.add("mug", 1_200, 0), QuantityError);
    cart.add("mug", 1_200, 98);
    assert.throws(() => cart.add("mug", 1_200, 2), QuantityError);
    assert.equal(cart.lines()[0].quantity, 98);
  });

  it("removes a line", () => {
    const cart = new Cart();
    cart.add("mug", 1_200, 1);
    cart.add("tea", 800, 1);
    cart.remove("mug");
    cart.remove("kettle");
    assert.deepEqual(cart.lines().map((line) => line.sku), ["tea"]);
  });

  it("sums the subtotal", () => {
    const cart = new Cart();
    cart.add("mug", 1_200, 2);
    cart.add("tea", 850, 3);
    assert.equal(cart.subtotal(), 4_950);
  });
});
