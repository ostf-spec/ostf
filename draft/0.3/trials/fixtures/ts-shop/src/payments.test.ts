// SPDX-License-Identifier: Apache-2.0
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AuditLog } from "./audit.ts";
import type { Cents } from "./money.ts";
import { AmountError, DeclineError, KeyReusedError, MAX_CHARGE, Processor, validateAmount, type Gateway } from "./payments.ts";

/** A gateway that counts charges and declines while `decline` is set. */
class FakeGateway implements Gateway {
  decline = "";
  charges = 0;

  async charge(_account: string, _amount: Cents): Promise<string> {
    if (this.decline) {
      throw new DeclineError(this.decline);
    }
    this.charges += 1;
    return `txn-${this.charges}`;
  }

  async refund(_txn: string, _amount: Cents): Promise<void> {}
}

const testTime = new Date("2026-03-01T12:00:00Z");

function newProcessor(): { processor: Processor; gateway: FakeGateway; audit: AuditLog } {
  const gateway = new FakeGateway();
  const audit = new AuditLog(() => testTime);
  return { processor: new Processor(gateway, audit), gateway, audit };
}

describe("validateAmount", () => {
  it("rejects amounts out of range", () => {
    for (const amount of [0, -1, 0.5, MAX_CHARGE + 1]) {
      assert.throws(() => validateAmount(amount), AmountError, `amount ${amount}`);
    }
  });

  it("accepts one cent and the maximum", () => {
    validateAmount(1);
    validateAmount(MAX_CHARGE);
  });
});

describe("Processor", () => {
  // @req R-IDEMPOTENT-CHARGE
  it("returns the first receipt on retry", async () => {
    const { processor, gateway } = newProcessor();
    const first = await processor.charge("order-1", "acct-1", 2_500);
    const second = await processor.charge("order-1", "acct-1", 2_500);
    assert.equal(gateway.charges, 1);
    assert.deepEqual(second, first);
  });

  it("rejects a reused key with another amount", async () => {
    const { processor } = newProcessor();
    await processor.charge("order-1", "acct-1", 2_500);
    await assert.rejects(processor.charge("order-1", "acct-1", 9_900), KeyReusedError);
  });

  // @req R-CHARGE-DECLINE
  it("does not remember a declined charge", async () => {
    const { processor, gateway } = newProcessor();
    gateway.decline = "insufficient funds";
    await assert.rejects(processor.charge("order-1", "acct-1", 2_500), { name: "DeclineError", reason: "insufficient funds" });
    gateway.decline = "";
    const receipt = await processor.charge("order-1", "acct-1", 2_500);
    assert.equal(receipt.amount, 2_500);
  });

  it("appends an audit entry", async () => {
    const { processor, audit } = newProcessor();
    const receipt = await processor.charge("order-1", "acct-1", 2_500);
    assert.deepEqual(audit.entries(), [
      { time: testTime, account: "acct-1", action: "charge", amount: 2_500, ref: receipt.id },
    ]);
  });
});
