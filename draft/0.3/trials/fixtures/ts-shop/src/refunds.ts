// SPDX-License-Identifier: Apache-2.0
import { formatCents, type Cents } from "./money.ts";
import type { Processor } from "./payments.ts";

/** The refund total per account and UTC day above which a refund needs a second approval: 500.00. */
export const DAILY_REFUND_LIMIT: Cents = 50_000;

/** A request to refund `amount` of the charge with `receiptId`. */
export interface RefundRequest {
  receiptId: string;
  amount: Cents;
  /** The second approver, when there is one. */
  approvedBy?: string;
}

/** Thrown for a refund above what is left of its charge. */
export class RefundTooLargeError extends Error {
  constructor(amount: Cents, left: Cents) {
    super(`refund of ${formatCents(amount)} exceeds the ${formatCents(left)} left on the charge`);
    this.name = "RefundTooLargeError";
  }
}

/** Thrown for a refund above the daily limit without a second approver. */
export class NeedsApprovalError extends Error {
  constructor(amount: Cents) {
    super(`refund of ${formatCents(amount)} is above the daily limit and needs a second approval`);
    this.name = "NeedsApprovalError";
  }
}

/** Thrown for a refund of a charge that does not exist. */
export class UnknownReceiptError extends Error {
  constructor(id: string) {
    super(`unknown receipt ${id}`);
    this.name = "UnknownReceiptError";
  }
}

/**
 * Rejects a refund that is not positive or exceeds what is left of its
 * charge, and one that takes the account's refunds for the day above
 * DAILY_REFUND_LIMIT without a second approval.
 */
export function checkRefundLimit(amount: Cents, leftOnCharge: Cents, refundedToday: Cents, approved: boolean): void {
  if (amount <= 0 || amount > leftOnCharge) {
    throw new RefundTooLargeError(amount, leftOnCharge);
  }
  if (refundedToday + amount > DAILY_REFUND_LIMIT && !approved) {
    throw new NeedsApprovalError(amount);
  }
}

/** Refunds earlier charges within the refund limit. It keeps what was refunded of each charge and of each account per UTC day. */
export class Refunder {
  private readonly processor: Processor;
  private readonly now: () => Date;
  private readonly refunded = new Map<string, Cents>();
  private readonly daily = new Map<string, Cents>();

  constructor(processor: Processor, now: () => Date = () => new Date()) {
    this.processor = processor;
    this.now = now;
  }

  /** Refunds `req.amount` of an earlier charge to the card that was charged, and records it in the audit log. */
  // @req R-REFUND-ORIGINAL
  async refund(req: RefundRequest): Promise<void> {
    const receipt = this.processor.receipt(req.receiptId);
    if (!receipt) {
      throw new UnknownReceiptError(req.receiptId);
    }
    const day = dayKey(receipt.account, this.now());
    const refunded = this.refunded.get(receipt.id) ?? 0;
    const today = this.daily.get(day) ?? 0;
    checkRefundLimit(req.amount, receipt.amount - refunded, today, Boolean(req.approvedBy));
    // Count the refund before awaiting the gateway, so that a concurrent refund sees it.
    this.refunded.set(receipt.id, refunded + req.amount);
    this.daily.set(day, today + req.amount);
    try {
      await this.processor.gateway.refund(receipt.txn, req.amount);
    } catch (err) {
      this.refunded.set(receipt.id, (this.refunded.get(receipt.id) ?? 0) - req.amount);
      this.daily.set(day, (this.daily.get(day) ?? 0) - req.amount);
      throw err;
    }
    this.processor.audit.append({ account: receipt.account, action: "refund", amount: req.amount, ref: receipt.id });
  }
}

/** Keys the daily refund total by account and UTC calendar day. */
// @req D-REFUND-LEDGER
function dayKey(account: string, at: Date): string {
  return `${account}/${at.toISOString().slice(0, 10)}`;
}
