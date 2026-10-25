// SPDX-License-Identifier: Apache-2.0
import type { Sessions } from "./accounts.ts";
import type { Cart, CartLine } from "./cart.ts";
import type { Stock } from "./inventory.ts";
import type { Processor, Receipt } from "./payments.ts";
import { price, type Discount, type Quote, type Region } from "./pricing.ts";

/** A placed order. */
export interface Order {
  account: string;
  lines: CartLine[];
  quote: Quote;
  receipt: Receipt;
}

/** Thrown when checking out a cart with no lines. */
export class EmptyCartError extends Error {
  constructor() {
    super("cannot check out an empty cart");
    this.name = "EmptyCartError";
  }
}

/** What checkout depends on. Tests pass their own. */
export interface CheckoutDeps {
  sessions: Sessions;
  stock: Stock;
  payments: Processor;
  region: Region;
  now?: () => Date;
}

/** Places orders. */
export class Checkout {
  private readonly deps: CheckoutDeps;

  constructor(deps: CheckoutDeps) {
    this.deps = deps;
  }

  /**
   * Checks out `cart` for the customer who holds the session `token`. It
   * prices the cart, reserves its stock, charges the customer under the
   * idempotency `key` and confirms the reservation. A failed charge releases
   * the reserved stock.
   */
  // @req R-CHECKOUT-SESSION
  async placeOrder(token: string, cart: Cart, discount: Discount | undefined, key: string): Promise<Order> {
    const { sessions, stock, payments, region, now = () => new Date() } = this.deps;
    const account = sessions.validate(token);
    const lines = cart.lines();
    if (lines.length === 0) {
      throw new EmptyCartError();
    }
    const quote = price(cart.subtotal(), discount, region, account.taxExempt, now());
    const hold = stock.reserve(new Map(lines.map((line) => [line.sku, line.quantity])));
    let receipt: Receipt;
    try {
      receipt = await payments.charge(key, account.id, quote.total);
    } catch (err) {
      stock.release(hold.id);
      throw err;
    }
    stock.confirm(hold.id);
    return { account: account.id, lines, quote, receipt };
  }
}
