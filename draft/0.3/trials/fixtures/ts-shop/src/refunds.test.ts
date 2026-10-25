// SPDX-License-Identifier: Apache-2.0
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AuditLog } from "./audit.ts";
import type { Cents } from "./money.ts";
import { Processor, type Gateway } from "./payments.ts";
import { checkRefundLimit, NeedsApprovalError, Refunder, RefundTooLargeError } from "./refunds.ts";

/** A gateway that approves every charge and records refunds by transaction. */
class RecordingGateway implements Gateway {
  private charges = 0;
  readonly refunds = new Map<string, Cents>();

  async charge(_account: string, _amount: Cents): Promise<string> {
    this.charges += 1;
    return `txn-${this.charges}`;
  }

  async refund(txn: string, amount: Cents): Promise<void> {
    this.refunds.set(txn, (this.refunds.get(txn) ?? 0) + amount);
  }
}

const testTime = new Date("2026-03-01T12:00:00Z");

function newProcessor(): { processor: Processor; gateway: RecordingGateway; audit: AuditLog } {
  const gateway = new RecordingGateway();
  const audit = new AuditLog(() => testTime);
  return { processor: new Processor(gateway, audit), gateway, audit };
}

describe("checkRefundLimit", () => {
  it("rejects more than is left on the charge", () => {
    assert.throws(() => checkRefundLimit(6_000, 5_000, 0, false), RefundTooLargeError);
    assert.throws(() => checkRefundLimit(0, 5_000, 0, false), RefundTooLargeError);
  });

  it("needs a second approval above the daily limit", () => {
    assert.throws(() => checkRefundLimit(2_000, 5_000, 49_000, false), NeedsApprovalError);
  });

  it("allows a refund within limits or approved", () => {
    checkRefundLimit(2_000, 5_000, 0, false);
    checkRefundLimit(2_000, 5_000, 49_000, true);
  });
});

describe("Refunder", () => {
  // @req R-AUDIT-MONEY
  it("refunds to the original transaction", async () => {
    const { processor, gateway, audit } = newProcessor();
    const receipt = await processor.charge("order-1", "acct-1", 5_000);
    const refunder = new Refunder(processor, () => testTime);
    await refunder.refund({ receiptId: receipt.id, amount: 1_500 });
    assert.equal(gateway.refunds.get(receipt.txn), 1_500);
    const last = audit.entries().at(-1);
    assert.equal(last?.action, "refund");
    assert.equal(last?.amount, 1_500);
    assert.equal(last?.ref, receipt.id);
    await assert.rejects(refunder.refund({ receiptId: receipt.id, amount: 4_000 }), RefundTooLargeError);
  });

  it("totals refunds per account and UTC day", async () => {
    const { processor } = newProcessor();
    let now = testTime;
    const refunder = new Refunder(processor, () => now);
    const a = await processor.charge("order-1", "acct-1", 40_000);
    const b = await processor.charge("order-2", "acct-1", 40_000);
    await refunder.refund({ receiptId: a.id, amount: 40_000 });
    await assert.rejects(refunder.refund({ receiptId: b.id, amount: 20_000 }), NeedsApprovalError);
    now = new Date(testTime.getTime() + 24 * 60 * 60 * 1000);
    await refunder.refund({ receiptId: b.id, amount: 20_000 });
  });
});
