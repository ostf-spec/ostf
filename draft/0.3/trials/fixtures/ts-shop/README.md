<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# shop

A small online shop in TypeScript, with no dependencies and no build step. Amounts are integer cents throughout.

| Module | What it does |
| --- | --- |
| `src/cart.ts` | Cart lines and subtotal |
| `src/pricing.ts` | Discount codes with a fifty percent cap, and sales tax by region |
| `src/inventory.ts` | Stock on hand and time-limited reservations |
| `src/checkout.ts` | Prices a cart, reserves stock, charges the customer and confirms the reservation |
| `src/payments.ts` | Charges with an idempotency key, through a card `Gateway` interface |
| `src/refunds.ts` | Refunds within a daily limit, back to the original charge |
| `src/accounts.ts` | Registration, login with lockout, and idle-expiring sessions |
| `src/audit.ts` | Append-only audit log of charges and refunds |
| `src/money.ts` | The `Cents` type and formatting |

The tests use fake gateways, so nothing talks to a network.

## Tests

Requires Node 26 or later, which runs TypeScript directly by stripping types; the code therefore uses only erasable syntax and imports local files with their `.ts` extension. From this directory:

```sh
node --test
```

`npm test` runs the same command.
