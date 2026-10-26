// SPDX-License-Identifier: Apache-2.0
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { BadCredentialsError, LOCKOUT_MS, LockedError, MAX_FAILED_LOGINS, SESSION_IDLE_MS, SessionError, Sessions } from "./accounts.ts";

function newSessions(): { sessions: Sessions; clock: { t: number } } {
  const clock = { t: Date.parse("2026-03-01T12:00:00Z") };
  const sessions = new Sessions(() => new Date(clock.t));
  sessions.register("ana@example.com", "correct horse");
  return { sessions, clock };
}

describe("Sessions", () => {
  it("logs in with the right password only", () => {
    const { sessions } = newSessions();
    assert.throws(() => sessions.login("ana@example.com", "wrong"), BadCredentialsError);
    assert.ok(sessions.login("ana@example.com", "correct horse"));
    const stored = sessions["byEmail"].get("ana@example.com");
    assert.equal(stored?.salt.length, 16);
    assert.ok(!stored?.hash.includes("correct horse"));
  });

  // @req R-LOGIN-LOCKOUT
  it("locks the account after five failures", () => {
    const { sessions, clock } = newSessions();
    for (let i = 0; i < MAX_FAILED_LOGINS; i++) {
      assert.throws(() => sessions.login("ana@example.com", "guess"), BadCredentialsError);
    }
    assert.throws(() => sessions.login("ana@example.com", "correct horse"), LockedError);
    clock.t += LOCKOUT_MS;
    assert.ok(sessions.login("ana@example.com", "correct horse"));
  });

  // @req R-SESSION-EXPIRY
  it("expires a session after 30 idle minutes", () => {
    const { sessions, clock } = newSessions();
    const token = sessions.login("ana@example.com", "correct horse");
    clock.t += SESSION_IDLE_MS - 1_000;
    assert.equal(sessions.validate(token).email, "ana@example.com");
    clock.t += SESSION_IDLE_MS;
    assert.throws(() => sessions.validate(token), (err: unknown) => err instanceof SessionError && err.expired);
  });
});
