// SPDX-License-Identifier: Apache-2.0

// Package pricing prices orders: discount codes and sales tax, in integer cents.
package pricing

import "fmt"

// Money is an amount in integer cents. The shop never uses floating point
// for money.
type Money int64

// String formats m as dollars and cents, such as "12.05" or "-3.10".
func (m Money) String() string {
	sign := ""
	if m < 0 {
		sign, m = "-", -m
	}
	return fmt.Sprintf("%s%d.%02d", sign, m/100, m%100)
}

// roundHalfUp divides num by den and rounds a remainder of one half or more
// up. Both arguments must be positive or zero.
func roundHalfUp(num, den int64) int64 {
	return (num + den/2) / den
}
