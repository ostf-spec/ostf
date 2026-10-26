// SPDX-License-Identifier: Apache-2.0
package cart

import (
	"errors"
	"slices"
	"time"

	"example.com/shop/accounts"
	"example.com/shop/inventory"
	"example.com/shop/payments"
	"example.com/shop/pricing"
)

// ErrEmptyCart is returned when checking out a cart with no lines.
var ErrEmptyCart = errors.New("cart: cannot check out an empty cart")

// Order is a placed order.
type Order struct {
	Account string
	Lines   []Line
	Quote   pricing.Quote
	Receipt payments.Receipt
}

// Checkout places orders. Each field is a dependency that tests replace.
type Checkout struct {
	Sessions *accounts.Sessions
	Stock    *inventory.Stock
	Payments *payments.Processor
	Region   pricing.Region
	Now      func() time.Time
}

// PlaceOrder checks out c for the customer who holds the session token. It
// prices the cart, reserves its stock, charges the customer under the
// idempotency key and confirms the reservation. A failed charge releases
// the reserved stock.
// @req R-CHECKOUT-SESSION
func (co *Checkout) PlaceOrder(token string, c *Cart, d *pricing.Discount, key string) (Order, error) {
	acct, err := co.Sessions.Validate(token)
	if err != nil {
		return Order{}, err
	}
	if len(c.lines) == 0 {
		return Order{}, ErrEmptyCart
	}
	quote, err := pricing.Price(c.Subtotal(), d, co.Region, acct.TaxExempt, co.Now())
	if err != nil {
		return Order{}, err
	}
	items := make(map[string]int, len(c.lines))
	for _, l := range c.lines {
		items[l.SKU] = l.Quantity
	}
	hold, err := co.Stock.Reserve(items)
	if err != nil {
		return Order{}, err
	}
	receipt, err := co.Payments.Charge(key, acct.ID, quote.Total)
	if err != nil {
		co.Stock.Release(hold.ID)
		return Order{}, err
	}
	if err := co.Stock.Confirm(hold.ID); err != nil {
		return Order{}, err
	}
	return Order{Account: acct.ID, Lines: slices.Clone(c.lines), Quote: quote, Receipt: receipt}, nil
}
