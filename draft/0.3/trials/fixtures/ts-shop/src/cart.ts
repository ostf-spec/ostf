// SPDX-License-Identifier: Apache-2.0
import { cents, type Cents } from "./money.ts";

/** The largest quantity that one cart line may hold. */
export const MAX_QUANTITY = 99;

/** One product in a cart. */
export interface CartLine {
  sku: string;
  unitPrice: Cents;
  quantity: number;
}

/** Thrown when a line's quantity would leave 1 to MAX_QUANTITY. */
export class QuantityError extends RangeError {
  constructor(quantity: number) {
    super(`quantity must be between 1 and ${MAX_QUANTITY}, got ${quantity}`);
    this.name = "QuantityError";
  }
}

/** A customer's cart. Lines keep the order in which their products were first added. */
export class Cart {
  private readonly items: CartLine[] = [];

  /**
   * Puts `quantity` units of `sku` in the cart. A product already in the cart
   * gets a larger quantity on its existing line. On error the cart is unchanged.
   */
  add(sku: string, unitPrice: Cents, quantity: number): void {
    const i = indexOf(this.items, sku);
    const total = quantity + (i >= 0 ? this.items[i].quantity : 0);
    if (!Number.isInteger(quantity) || quantity < 1 || total > MAX_QUANTITY) {
      throw new QuantityError(total);
    }
    if (i >= 0) {
      this.items[i].quantity = total;
    } else {
      this.items.push({ sku, unitPrice: cents(unitPrice), quantity });
    }
  }

  /** Deletes the line for `sku`. Removing a product that is not in the cart does nothing. */
  // @req R-CART-REMOVE
  remove(sku: string): void {
    const i = indexOf(this.items, sku);
    if (i >= 0) {
      this.items.splice(i, 1);
    }
  }

  /** Returns a copy of the cart's lines. */
  lines(): CartLine[] {
    return this.items.map((line) => ({ ...line }));
  }

  /** The sum of unit price times quantity over all lines. */
  // @req R-CART-SUBTOTAL
  subtotal(): Cents {
    return this.items.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0);
  }
}

/** Returns the index of the line for `sku`, or -1. */
function indexOf(lines: CartLine[], sku: string): number {
  return lines.findIndex((line) => line.sku === sku);
}
