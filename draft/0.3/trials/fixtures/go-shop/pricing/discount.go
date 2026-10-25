// SPDX-License-Identifier: Apache-2.0
package pricing

import (
	"errors"
	"fmt"
	"time"
)

// MaxDiscountPercent is the largest share of a subtotal that a discount may take.
const MaxDiscountPercent = 50

// ErrDiscountExpired is returned for a discount code used after it expired.
var ErrDiscountExpired = errors.New("pricing: discount code has expired")

// Discount is a percentage discount code.
type Discount struct {
	Code    string
	Percent int64
	Expires time.Time
}

// ApplyDiscount returns the amount that d takes off subtotal at time now,
// rounded down to the cent and capped at MaxDiscountPercent.
// @req R-DISCOUNT-EXPIRY
func ApplyDiscount(subtotal Money, d Discount, now time.Time) (Money, error) {
	if !now.Before(d.Expires) {
		return 0, fmt.Errorf("%w: %s", ErrDiscountExpired, d.Code)
	}
	percent := min(d.Percent, MaxDiscountPercent)
	return subtotal * Money(percent) / 100, nil
}
