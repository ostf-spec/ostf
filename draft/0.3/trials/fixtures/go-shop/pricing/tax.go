// SPDX-License-Identifier: Apache-2.0
package pricing

// Region is a shipping region and its sales tax rate in parts per million,
// so that a rate of 14.975 percent is 149_750.
type Region struct {
	Code    string
	RatePPM int64
}

// Tax returns the sales tax on amount in region r, rounded half up to the
// cent. A tax-exempt customer pays no tax.
func Tax(amount Money, r Region, exempt bool) Money {
	if exempt || amount <= 0 {
		return 0
	}
	return Money(roundHalfUp(int64(amount)*r.RatePPM, 1_000_000))
}
