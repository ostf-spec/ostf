// SPDX-License-Identifier: Apache-2.0

// Package cart holds a customer's cart and turns it into an order at checkout.
package cart

import (
	"errors"
	"slices"

	"example.com/shop/pricing"
)

// MaxQuantity is the largest quantity that one cart line may hold.
const MaxQuantity = 99

// ErrQuantity is returned when a line's quantity would leave 1 to MaxQuantity.
var ErrQuantity = errors.New("cart: quantity must be between 1 and 99")

// Line is one product in a cart.
type Line struct {
	SKU       string
	UnitPrice pricing.Money
	Quantity  int
}

// Cart holds lines in the order their products were first added. The zero
// value is an empty cart.
type Cart struct {
	lines []Line
}

// Add puts qty units of sku in the cart. A product already in the cart gets
// a larger quantity on its existing line. On error the cart is unchanged.
func (c *Cart) Add(sku string, unitPrice pricing.Money, qty int) error {
	i := c.indexOf(sku)
	total := qty
	if i >= 0 {
		total += c.lines[i].Quantity
	}
	if qty < 1 || total > MaxQuantity {
		return ErrQuantity
	}
	if i >= 0 {
		c.lines[i].Quantity = total
		return nil
	}
	c.lines = append(c.lines, Line{SKU: sku, UnitPrice: unitPrice, Quantity: qty})
	return nil
}

// Remove deletes the line for sku. Removing a product that is not in the
// cart does nothing.
// @req R-CART-REMOVE
func (c *Cart) Remove(sku string) {
	if i := c.indexOf(sku); i >= 0 {
		c.lines = slices.Delete(c.lines, i, i+1)
	}
}

// Subtotal is the sum of unit price times quantity over all lines.
// @req R-CART-SUBTOTAL
func (c *Cart) Subtotal() pricing.Money {
	var sum pricing.Money
	for _, l := range c.lines {
		sum += l.UnitPrice * pricing.Money(l.Quantity)
	}
	return sum
}

// indexOf returns the index of the line for sku, or -1.
func (c *Cart) indexOf(sku string) int {
	return slices.IndexFunc(c.lines, func(l Line) bool { return l.SKU == sku })
}
