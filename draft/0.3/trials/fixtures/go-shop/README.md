<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# shop

A small online shop in Go, with no dependencies outside the standard library. Amounts are integer cents throughout.

| Package | What it does |
| --- | --- |
| `cart` | Cart lines and subtotal, and `Checkout`, which prices a cart, reserves stock, charges the customer and confirms the reservation |
| `pricing` | Discount codes with a fifty percent cap, and sales tax by region |
| `inventory` | Stock on hand and time-limited reservations |
| `payments` | Charges with an idempotency key, refunds within a daily limit, and an append-only audit log |
| `accounts` | Registration, login with lockout, and idle-expiring sessions |

The card gateway is an interface (`payments.Gateway`); the tests use fakes, so nothing talks to a network.

## Tests

Requires Go 1.27 or later. From this directory:

```sh
go test ./...
```
