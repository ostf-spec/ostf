// SPDX-License-Identifier: Apache-2.0
package pricing

import "time"

// Quote is the price of an order, broken down.
type Quote struct {
	Subtotal Money
	Discount Money
	Tax      Money
	Total    Money
}

// Price quotes an order: it takes the discount code d, when there is one, off
// subtotal, then adds sales tax on what is left.
func Price(subtotal Money, d *Discount, r Region, exempt bool, now time.Time) (Quote, error) {
	q := Quote{Subtotal: subtotal}
	if d != nil {
		off, err := ApplyDiscount(subtotal, *d, now)
		if err != nil {
			return Quote{}, err
		}
		q.Discount = off
	}
	q.Tax = Tax(subtotal-q.Discount, r, exempt)
	q.Total = subtotal - q.Discount + q.Tax
	return q, nil
}
