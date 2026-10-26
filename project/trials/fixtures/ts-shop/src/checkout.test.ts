// SPDX-License-Identifier: Apache-2.0
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { Sessions, SessionError } from "./accounts.ts";
import { AuditLog } from "./audit.ts";
import { Cart } from "./cart.ts";
import { Checkout, EmptyCartError } from "./checkout.ts";
import { Stock } from "./inventory.ts";
import type { Cents } from "./money.ts";
import { DeclineError, Processor, type Gateway } from "./payments.ts";

/** A gateway that approves every charge unless `decline` is set. */
class CardGateway implements Gateway {
  decline = "";

  async charge(_account: string, _amount: Cents): Promise<string> {
    if (this.decline) {
      throw new DeclineError(this.decline);
    }
    return "txn-1";
  }

  async refund(_txn: string, _amount: Cents): Promise<void> {}
}

function newShop(): { checkout: Checkout; stock: Stock; gateway: CardGateway; audit: AuditLog; token: string } {
  const now = () => new Date("2026-03-01T12:00:00Z");
  const sessions = new Sessions(now);
  sessions.register("ana@example.com", "correct horse");
  const token = sessions.login("ana@example.com", "correct horse");
  const stock = new Stock(now);
  stock.receive("mug", 5);
  const gateway = new CardGateway();
  const audit = new AuditLog(now);
  const checkout = new Checkout({
    sessions,
    stock,
    payments: new Processor(gateway, audit),
    region: { code: "QC", ratePpm: 149_750 },
    now,
  });
  return { checkout, stock, gateway, audit, token };
}

function cartOf(quantity: number): Cart {
  const cart = new Cart();
  cart.add("mug", 1_000, quantity);
  return cart;
}

describe("Checkout", () => {
  // @req R-CHECKOUT-ORDER
  it("places an order", async () => {
    const { checkout, stock, token } = newShop();
    const order = await checkout.placeOrder(token, cartOf(2), undefined, "order-1");
    assert.equal(order.quote.total, 2_300);
    assert.equal(order.receipt.amount, 2_300);
    assert.equal(stock.available("mug"), 3);
    await assert.rejects(checkout.placeOrder(token, new Cart(), undefined, "order-2"), EmptyCartError);
  });

  // @req R-CHECKOUT-SESSION
  it("needs a valid session", async () => {
    const { checkout, audit } = newShop();
    await assert.rejects(checkout.placeOrder("forged-token", cartOf(1), undefined, "order-1"), SessionError);
    assert.equal(audit.entries().length, 0);
  });

  // @req R-STOCK-RELEASE
  it("releases stock when the charge is declined", async () => {
    const { checkout, stock, gateway, token } = newShop();
    gateway.decline = "card expired";
    await assert.rejects(checkout.placeOrder(token, cartOf(4), undefined, "order-1"), DeclineError);
    assert.equal(stock.available("mug"), 5);
  });
});
