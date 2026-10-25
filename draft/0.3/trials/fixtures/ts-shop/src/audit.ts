// SPDX-License-Identifier: Apache-2.0
import type { Cents } from "./money.ts";

/** One audit record of money moving. */
export interface AuditEntry {
  time: Date;
  account: string;
  action: "charge" | "refund";
  amount: Cents;
  /** The receipt ID. */
  ref: string;
}

/** An append-only record of charges and refunds. It has no way to change or remove an entry. */
export class AuditLog {
  private readonly now: () => Date;
  private readonly log: AuditEntry[] = [];

  /** Creates an empty log that stamps entries with the time from `now`. */
  constructor(now: () => Date = () => new Date()) {
    this.now = now;
  }

  /** Stamps `entry` with the current time and adds it to the end of the log. */
  append(entry: Omit<AuditEntry, "time">): void {
    this.log.push({ ...entry, time: this.now() });
  }

  /** Returns a copy of the log, oldest entry first. */
  entries(): AuditEntry[] {
    return this.log.map((entry) => ({ ...entry, time: new Date(entry.time) }));
  }
}
