// SPDX-License-Identifier: Apache-2.0
import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto";

/** The number of consecutive failed logins that locks an account. */
export const MAX_FAILED_LOGINS = 5;
/** How long a locked account refuses logins: 15 minutes. */
export const LOCKOUT_MS = 15 * 60 * 1000;
/** How long a session lasts without use: 30 minutes. */
export const SESSION_IDLE_MS = 30 * 60 * 1000;

/** A registered customer. */
export interface Account {
  id: string;
  email: string;
  taxExempt: boolean;
}

/** Thrown when registering an email that already has an account. */
export class EmailTakenError extends Error {
  constructor(email: string) {
    super(`email ${email} is already registered`);
    this.name = "EmailTakenError";
  }
}

/** Thrown for a wrong email or password. */
export class BadCredentialsError extends Error {
  constructor() {
    super("wrong email or password");
    this.name = "BadCredentialsError";
  }
}

/** Thrown for a login to an account locked after too many failures. */
export class LockedError extends Error {
  constructor(until: Date) {
    super(`account locked until ${until.toISOString()}`);
    this.name = "LockedError";
  }
}

/** Thrown for a session token that is unknown or has expired. */
export class SessionError extends Error {
  readonly expired: boolean;

  constructor(expired: boolean) {
    super(expired ? "session expired" : "no such session");
    this.name = "SessionError";
    this.expired = expired;
  }
}

interface Credentials {
  account: Account;
  salt: Buffer;
  hash: Buffer;
  failed: number;
  lockedUntil: number;
}

interface Session {
  account: Account;
  lastUsed: number;
}

/** Accounts and their login sessions. */
export class Sessions {
  private readonly now: () => Date;
  private readonly byEmail = new Map<string, Credentials>();
  private readonly sessions = new Map<string, Session>();

  /** Creates an empty store that reads the current time from `now`. */
  constructor(now: () => Date = () => new Date()) {
    this.now = now;
  }

  /** Creates an account for `email` with a salted hash of `password`. */
  register(email: string, password: string, taxExempt = false): Account {
    if (this.byEmail.has(email)) {
      throw new EmailTakenError(email);
    }
    const salt = randomBytes(16);
    const account: Account = { id: `acct-${this.byEmail.size + 1}`, email, taxExempt };
    this.byEmail.set(email, { account, salt, hash: hashPassword(password, salt), failed: 0, lockedUntil: 0 });
    return account;
  }

  /**
   * Checks `email` and `password` and returns a new session token. After
   * MAX_FAILED_LOGINS consecutive failures the account is locked for
   * LOCKOUT_MS, and even the right password is refused until then.
   */
  login(email: string, password: string): string {
    const c = this.byEmail.get(email);
    if (!c) {
      throw new BadCredentialsError();
    }
    const now = this.now().getTime();
    if (now < c.lockedUntil) {
      throw new LockedError(new Date(c.lockedUntil));
    }
    if (!timingSafeEqual(hashPassword(password, c.salt), c.hash)) {
      c.failed += 1;
      if (c.failed >= MAX_FAILED_LOGINS) {
        c.failed = 0;
        c.lockedUntil = now + LOCKOUT_MS;
      }
      throw new BadCredentialsError();
    }
    c.failed = 0;
    const token = newToken();
    this.sessions.set(token, { account: c.account, lastUsed: now });
    return token;
  }

  /** Returns the account that holds the session `token` and extends the session. A session unused for SESSION_IDLE_MS has expired. */
  // @req R-SESSION-EXPIRY
  validate(token: string): Account {
    const session = this.sessions.get(token);
    if (!session) {
      throw new SessionError(false);
    }
    const now = this.now().getTime();
    if (now - session.lastUsed >= SESSION_IDLE_MS) {
      this.sessions.delete(token);
      throw new SessionError(true);
    }
    session.lastUsed = now;
    return session.account;
  }
}

/** Derives the stored hash of `password` with scrypt. */
// @req R-PASSWORD-HASH
function hashPassword(password: string, salt: Buffer): Buffer {
  return scryptSync(password, salt, 32);
}

/** Returns a random session token. */
function newToken(): string {
  return randomBytes(16).toString("base64url");
}
