// SPDX-License-Identifier: Apache-2.0
package pricing

import (
	"errors"
	"testing"
	"time"
)

func TestApplyDiscount(t *testing.T) {
	now := time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC)
	later := now.Add(24 * time.Hour)

	t.Run("takes_the_percentage", func(t *testing.T) {
		got, err := ApplyDiscount(10_000, Discount{Code: "TEN", Percent: 10, Expires: later}, now)
		if err != nil || got != 1_000 {
			t.Fatalf("ApplyDiscount = %v, %v; want 10.00, nil", got, err)
		}
	})
	t.Run("rounds_down", func(t *testing.T) {
		got, _ := ApplyDiscount(999, Discount{Code: "FIFTEEN", Percent: 15, Expires: later}, now)
		if got != 149 {
			t.Fatalf("15%% of 9.99 = %v; want 1.49", got)
		}
	})
	t.Run("caps_at_fifty_percent", func(t *testing.T) {
		got, _ := ApplyDiscount(10_000, Discount{Code: "TYPO", Percent: 100, Expires: later}, now)
		if got != 5_000 {
			t.Fatalf("100%% code took %v off 100.00; want 50.00", got)
		}
	})
	t.Run("rejects_expired", func(t *testing.T) {
		_, err := ApplyDiscount(10_000, Discount{Code: "OLD", Percent: 10, Expires: now}, now)
		if !errors.Is(err, ErrDiscountExpired) {
			t.Fatalf("expired code: err = %v; want ErrDiscountExpired", err)
		}
	})
}
