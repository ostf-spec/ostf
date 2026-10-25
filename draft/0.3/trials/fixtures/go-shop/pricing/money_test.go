// SPDX-License-Identifier: Apache-2.0
package pricing

import "testing"

// @req R-MONEY-CENTS
func TestMoneyString(t *testing.T) {
	for m, want := range map[Money]string{1205: "12.05", -310: "-3.10", 7: "0.07"} {
		if got := m.String(); got != want {
			t.Errorf("Money(%d).String() = %q; want %q", int64(m), got, want)
		}
	}
}
