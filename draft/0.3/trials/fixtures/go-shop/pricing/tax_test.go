// SPDX-License-Identifier: Apache-2.0
package pricing

import (
	"testing"
	"time"
)

var quebec = Region{Code: "QC", RatePPM: 149_750}

func TestTax(t *testing.T) {
	tests := []struct {
		amount, want Money
	}{
		{10_000, 1_498}, // 14.975 rounds half up to 14.98
		{100, 15},
		{0, 0},
	}
	for _, tc := range tests {
		if got := Tax(tc.amount, quebec, false); got != tc.want {
			t.Errorf("Tax(%v) = %v; want %v", tc.amount, got, tc.want)
		}
	}
}

// @req R-TAX-EXEMPT
func TestTaxExempt(t *testing.T) {
	if got := Tax(10_000, quebec, true); got != 0 {
		t.Fatalf("exempt tax = %v; want 0.00", got)
	}
}

func TestPrice(t *testing.T) {
	now := time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC)
	d := &Discount{Code: "TEN", Percent: 10, Expires: now.Add(time.Hour)}
	q, err := Price(10_000, d, quebec, false, now)
	if err != nil {
		t.Fatal(err)
	}
	want := Quote{Subtotal: 10_000, Discount: 1_000, Tax: 1_348, Total: 10_348}
	if q != want {
		t.Fatalf("Price = %+v; want %+v", q, want)
	}
}
