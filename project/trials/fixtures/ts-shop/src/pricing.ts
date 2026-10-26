// SPDX-License-Identifier: Apache-2.0
import type { Cents } from "./money.ts";

/** The largest share of a subtotal that a discount may take, in percent. */
export const MAX_DISCOUNT_PERCENT = 50;

/** A percentage discount code. */
export interface Discount {
  code: string;
  percent: number;
  expires: Date;
}

/** A shipping region and its sales tax rate in parts per million, so that 14.975 percent is 149_750. */
export interface Region {
  code: string;
  ratePpm: number;
}

/** The price of an order, broken down. */
export interface Quote {
  subtotal: Cents;
  discount: Cents;
  tax: Cents;
  total: Cents;
}

/** Thrown for a discount code used after it expired. */
export class DiscountExpiredError extends Error {
  constructor(code: string) {
    super(`discount code ${code} has expired`);
    this.name = "DiscountExpiredError";
  }
}

/**
 * Returns the amount that `d` takes off `subtotal` at time `now`, rounded
 * down to the cent and capped at MAX_DISCOUNT_PERCENT.
 */
// @req R-DISCOUNT-EXPIRY
export function applyDiscount(subtotal: Cents, d: Discount, now: Date): Cents {
  if (now.getTime() >= d.expires.getTime()) {
    throw new DiscountExpiredError(d.code);
  }
  const percent = Math.min(d.percent, MAX_DISCOUNT_PERCENT);
  return Math.floor((subtotal * percent) / 100);
}

/** Returns the sales tax on `amount` in region `r`, rounded half up to the cent. A tax-exempt customer pays none. */
export function tax(amount: Cents, r: Region, exempt: boolean): Cents {
  if (exempt || amount <= 0) {
    return 0;
  }
  return roundHalfUp(amount * r.ratePpm, 1_000_000);
}

/** Quotes an order: takes the discount code `d`, when given, off `subtotal`, then adds sales tax on what is left. */
export function price(subtotal: Cents, d: Discount | undefined, r: Region, exempt: boolean, now: Date): Quote {
  const discount = d ? applyDiscount(subtotal, d, now) : 0;
  const salesTax = tax(subtotal - discount, r, exempt);
  return { subtotal, discount, tax: salesTax, total: subtotal - discount + salesTax };
}

/** Divides `num` by `den`, rounding a remainder of one half or more up. Both must be zero or more. */
function roundHalfUp(num: number, den: number): number {
  return Math.floor((num + den / 2) / den);
}
