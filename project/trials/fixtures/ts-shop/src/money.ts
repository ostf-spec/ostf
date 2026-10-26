// SPDX-License-Identifier: Apache-2.0

/** An amount of money in integer cents. The shop never uses fractions of a cent. */
export type Cents = number;

/** Returns `value` as Cents, or throws when it is not a whole number of cents. */
export function cents(value: number): Cents {
  if (!Number.isSafeInteger(value)) {
    throw new RangeError(`not a whole number of cents: ${value}`);
  }
  return value;
}

/** Formats an amount as dollars and cents, such as "12.05" or "-3.10". */
export function formatCents(amount: Cents): string {
  const sign = amount < 0 ? "-" : "";
  const abs = Math.abs(amount);
  return `${sign}${Math.trunc(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}
