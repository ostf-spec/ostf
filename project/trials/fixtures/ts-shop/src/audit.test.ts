// SPDX-License-Identifier: Apache-2.0
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { AuditLog } from "./audit.ts";

const testTime = new Date("2026-03-01T12:00:00Z");

describe("AuditLog", () => {
  it("returns copies of its entries", () => {
    const log = new AuditLog(() => testTime);
    log.append({ account: "acct-1", action: "charge", amount: 100, ref: "rcpt-1" });
    const entries = log.entries();
    entries[0].amount = 1;
    entries[0].time.setTime(0);
    entries.pop();
    assert.equal(log.entries()[0].amount, 100);
    assert.deepEqual(log.entries()[0].time, testTime);
  });

  it("stamps entries with its clock", () => {
    const log = new AuditLog(() => testTime);
    log.append({ account: "acct-1", action: "refund", amount: 100, ref: "rcpt-1" });
    assert.deepEqual(log.entries()[0].time, testTime);
  });
});
