// SPDX-License-Identifier: Apache-2.0
package payments

import "testing"

func TestRefundLimit(t *testing.T) {
	acct := Account{RefundedToday: 900, DailyLimit: 1000}
	if err := CheckRefundLimit(Refund{OrderTotal: 50, Amount: 60}, acct); err != ErrRefundTooLarge {
		t.Fatalf("over the order total: got %v", err)
	}
	if err := CheckRefundLimit(Refund{OrderTotal: 500, Amount: 200}, acct); err != ErrNeedsApproval {
		t.Fatalf("over the daily limit without approval: got %v", err)
	}
	if err := CheckRefundLimit(Refund{OrderTotal: 500, Amount: 200, Approved: true}, acct); err != nil {
		t.Fatalf("approved refund: got %v", err)
	}
}
