// SPDX-License-Identifier: Apache-2.0
package payments

import "testing"

// @req PAY-123
func TestChargeRetry(t *testing.T) {
	calls := 0
	svc := NewService(func(amount int) Receipt {
		calls++
		return Receipt{ID: "rcpt-1", Amount: amount}
	})
	first := svc.Charge("key-1", 25)
	second := svc.Charge("key-1", 25)
	if calls != 1 {
		t.Fatalf("gateway called %d times; want 1", calls)
	}
	if first != second {
		t.Fatalf("retry returned %v; want %v", second, first)
	}
}
