// SPDX-License-Identifier: Apache-2.0
import type { AuditLog } from "./audit.ts";
import { formatCents, type Cents } from "./money.ts";

/** The largest amount that a single charge may take: 10,000.00. */
export const MAX_CHARGE: Cents = 1_000_000;

/**
 * The card processor. `charge` resolves to the gateway's transaction ID;
 * `refund` sends money back to the card of that transaction.
 */
export interface Gateway {
  charge(account: string, amount: Cents): Promise<string>;
  refund(txn: string, amount: Cents): Promise<void>;
}

/** A successful charge. */
export interface Receipt {
  id: string;
  account: string;
  amount: Cents;
  txn: string;
}

/** Thrown for a charge of zero, less, a fraction of a cent, or more than MAX_CHARGE. */
export class AmountError extends RangeError {
  constructor(amount: Cents) {
    super(`charge must be more than 0.00 and at most 10,000.00, got ${formatCents(amount)}`);
    this.name = "AmountError";
  }
}

/** Thrown by a Gateway that declines a charge. */
export class DeclineError extends Error {
  readonly reason: string;

  constructor(reason: string) {
    super(`charge declined: ${reason}`);
    this.name = "DeclineError";
    this.reason = reason;
  }
}

/** Thrown when an idempotency key comes back with a different charge. */
export class KeyReusedError extends Error {
  constructor(key: string) {
    super(`idempotency key ${key} reused for a different charge`);
    this.name = "KeyReusedError";
  }
}

/** Rejects a charge that is zero, negative, a fraction of a cent or above MAX_CHARGE. */
export function validateAmount(amount: Cents): void {
  if (!Number.isSafeInteger(amount) || amount <= 0 || amount > MAX_CHARGE) {
    throw new AmountError(amount);
  }
}

interface Attempt {
  account: string;
  amount: Cents;
  receipt: Promise<Receipt>;
}

/** Charges through a gateway and keeps each charge under its idempotency key. */
export class Processor {
  readonly gateway: Gateway;
  readonly audit: AuditLog;
  private readonly byKey = new Map<string, Attempt>();
  private readonly byId = new Map<string, Receipt>();

  constructor(gateway: Gateway, audit: AuditLog) {
    this.gateway = gateway;
    this.audit = audit;
  }

  /**
   * Charges `amount` to `account` under the idempotency `key`. A retry with
   * the same key returns the first receipt without calling the gateway again.
   * A declined charge is not remembered, so the customer can retry it.
   */
  // @req R-IDEMPOTENT-CHARGE
  async charge(key: string, account: string, amount: Cents): Promise<Receipt> {
    validateAmount(amount);
    const known = this.byKey.get(key);
    if (known) {
      if (known.account !== account || known.amount !== amount) {
        throw new KeyReusedError(key);
      }
      return known.receipt;
    }
    const receipt = this.gateway.charge(account, amount).then((txn) => {
      const r: Receipt = { id: `rcpt-${key}`, account, amount, txn };
      this.byId.set(r.id, r);
      this.audit.append({ account, action: "charge", amount, ref: r.id });
      return r;
    });
    this.byKey.set(key, { account, amount, receipt });
    try {
      return await receipt;
    } catch (err) {
      this.byKey.delete(key);
      throw err;
    }
  }

  /** Returns the receipt with the given ID, which names the gateway transaction that a refund must go back to. */
  // @req R-REFUND-ORIGINAL
  receipt(id: string): Receipt | undefined {
    return this.byId.get(id);
  }
}
