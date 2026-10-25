// SPDX-License-Identifier: Apache-2.0
package payments

import (
	"errors"
	"testing"
	"time"

	"example.com/shop/pricing"
)

func TestCheckRefundLimit(t *testing.T) {
	tests := []struct {
		name                string
		amount, left, today pricing.Money
		approved            bool
		want                error
	}{
		{"within limits", 2_000, 5_000, 0, false, nil},
		{"more than is left", 6_000, 5_000, 0, false, ErrRefundTooLarge},
		{"zero", 0, 5_000, 0, false, ErrRefundTooLarge},
		{"over the daily limit", 2_000, 5_000, 49_000, false, ErrNeedsApproval},
		{"over the daily limit, approved", 2_000, 5_000, 49_000, true, nil},
	}
	for _, tc := range tests {
		err := CheckRefundLimit(tc.amount, tc.left, tc.today, tc.approved)
		if !errors.Is(err, tc.want) {
			t.Errorf("%s: err = %v; want %v", tc.name, err, tc.want)
		}
	}
}

// @req R-AUDIT-MONEY
func TestRefund(t *testing.T) {
	p, g, log := newProcessor()
	rcpt, err := p.Charge("order-1", "acct-1", 5_000)
	if err != nil {
		t.Fatal(err)
	}
	r := NewRefunder(p, func() time.Time { return testTime })
	if err := r.Refund(RefundRequest{ReceiptID: rcpt.ID, Amount: 1_500}); err != nil {
		t.Fatal(err)
	}
	if got := g.refunds[rcpt.Txn]; got != 1_500 {
		t.Fatalf("refunded to %s: %v; want 15.00", rcpt.Txn, got)
	}
	entries := log.Entries()
	last := entries[len(entries)-1]
	if last.Action != "refund" || last.Amount != 1_500 || last.Ref != rcpt.ID {
		t.Fatalf("last audit entry = %+v; want the refund", last)
	}
	err = r.Refund(RefundRequest{ReceiptID: rcpt.ID, Amount: 4_000})
	if !errors.Is(err, ErrRefundTooLarge) {
		t.Fatalf("refund beyond the charge: err = %v; want ErrRefundTooLarge", err)
	}
}

func TestRefundDailyLimit(t *testing.T) {
	p, _, _ := newProcessor()
	now := testTime
	r := NewRefunder(p, func() time.Time { return now })
	a, _ := p.Charge("order-1", "acct-1", 40_000)
	b, _ := p.Charge("order-2", "acct-1", 40_000)
	if err := r.Refund(RefundRequest{ReceiptID: a.ID, Amount: 40_000}); err != nil {
		t.Fatal(err)
	}
	err := r.Refund(RefundRequest{ReceiptID: b.ID, Amount: 20_000})
	if !errors.Is(err, ErrNeedsApproval) {
		t.Fatalf("second refund the same day: err = %v; want ErrNeedsApproval", err)
	}
	now = now.Add(24 * time.Hour)
	if err := r.Refund(RefundRequest{ReceiptID: b.ID, Amount: 20_000}); err != nil {
		t.Fatalf("refund the next UTC day: %v", err)
	}
}
