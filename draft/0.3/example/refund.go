// SPDX-License-Identifier: Apache-2.0

// Package payments is a small source tree traced with OSTF 0.3. It is an
// illustration of the format, not a production payment implementation.
package payments

import "errors"

// Errors returned by CheckRefundLimit.
var (
	ErrRefundTooLarge = errors.New("refund exceeds the original order")
	ErrNeedsApproval  = errors.New("refund above the daily limit needs a second approval")
)

// Refund is a refund request against an order.
type Refund struct {
	OrderTotal int
	Amount     int
	Approved   bool
}

// Account carries what was already refunded today and the account's daily limit.
type Account struct {
	RefundedToday int
	DailyLimit    int
}

// CheckRefundLimit rejects a refund above the order total and requires a
// second approval when the account's daily limit would be exceeded.
func CheckRefundLimit(r Refund, acct Account) error {
	if r.Amount > r.OrderTotal {
		return ErrRefundTooLarge
	}
	if acct.RefundedToday+r.Amount > acct.DailyLimit && !r.Approved {
		return ErrNeedsApproval
	}
	return nil
}
