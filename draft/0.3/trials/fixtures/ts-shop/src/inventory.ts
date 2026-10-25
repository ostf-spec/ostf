// SPDX-License-Identifier: Apache-2.0

/** How long a reservation holds stock before it expires: 15 minutes. */
export const HOLD_MS = 15 * 60 * 1000;

/** A hold on quantities of several SKUs until it expires. */
export interface Reservation {
  id: string;
  items: ReadonlyMap<string, number>;
  expires: Date;
}

/** Thrown when a reservation asks for more than is available. */
export class InsufficientStockError extends Error {
  constructor(sku: string) {
    super(`insufficient stock of ${sku}`);
    this.name = "InsufficientStockError";
  }
}

/** Thrown when confirming an unknown or expired reservation. */
export class NoReservationError extends Error {
  constructor(id: string) {
    super(`no reservation ${id}`);
    this.name = "NoReservationError";
  }
}

/** The stock on hand per SKU and the reservations against it. */
export class Stock {
  private readonly now: () => Date;
  private readonly onHand = new Map<string, number>();
  private readonly holds = new Map<string, Reservation>();
  private seq = 0;

  /** Creates empty stock that reads the current time from `now`. */
  constructor(now: () => Date = () => new Date()) {
    this.now = now;
  }

  /** Adds `quantity` units of `sku` to the stock on hand. */
  receive(sku: string, quantity: number): void {
    this.onHand.set(sku, (this.onHand.get(sku) ?? 0) + quantity);
  }

  /** Returns the units of `sku` that no unexpired reservation holds. */
  // @req D-RESERVATION-HOLD
  available(sku: string): number {
    const now = this.now().getTime();
    let n = this.onHand.get(sku) ?? 0;
    for (const hold of this.holds.values()) {
      if (now < hold.expires.getTime()) {
        n -= hold.items.get(sku) ?? 0;
      }
    }
    return n;
  }

  /** Holds every quantity in `items` for HOLD_MS, or holds nothing when any SKU is short. */
  reserve(items: ReadonlyMap<string, number>): Reservation {
    for (const [sku, quantity] of items) {
      if (quantity > this.available(sku)) {
        throw new InsufficientStockError(sku);
      }
    }
    this.seq += 1;
    const hold: Reservation = {
      id: `hold-${this.seq}`,
      items: new Map(items),
      expires: new Date(this.now().getTime() + HOLD_MS),
    };
    this.holds.set(hold.id, hold);
    return hold;
  }

  /** Returns the stock held by reservation `id`. Releasing an unknown or expired reservation does nothing. */
  release(id: string): void {
    this.holds.delete(id);
  }

  /** Turns reservation `id` into a sale: its quantities leave the stock on hand. An expired reservation cannot be confirmed. */
  confirm(id: string): void {
    const hold = this.holds.get(id);
    this.holds.delete(id);
    if (!hold || this.now().getTime() >= hold.expires.getTime()) {
      throw new NoReservationError(id);
    }
    for (const [sku, quantity] of hold.items) {
      this.onHand.set(sku, (this.onHand.get(sku) ?? 0) - quantity);
    }
  }
}
