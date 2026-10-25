// SPDX-License-Identifier: Apache-2.0
package cart

import (
	"errors"
	"testing"
	"time"

	"example.com/shop/accounts"
	"example.com/shop/inventory"
	"example.com/shop/payments"
	"example.com/shop/pricing"
)

// gateway approves every charge unless decline is set.
type gateway struct{ decline bool }

func (g *gateway) Charge(account string, amount pricing.Money) (string, error) {
	if g.decline {
		return "", &payments.DeclineError{Reason: "card expired"}
	}
	return "txn-1", nil
}

func (g *gateway) Refund(txn string, amount pricing.Money) error { return nil }

type shop struct {
	checkout *Checkout
	gateway  *gateway
	audit    *payments.AuditLog
	token    string
}

func newShop(t *testing.T) *shop {
	t.Helper()
	now := func() time.Time { return time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC) }
	sessions := accounts.NewSessions(now)
	if _, err := sessions.Register("ana@example.com", "correct horse", false); err != nil {
		t.Fatal(err)
	}
	token, err := sessions.Login("ana@example.com", "correct horse")
	if err != nil {
		t.Fatal(err)
	}
	stock := inventory.NewStock(now)
	stock.Receive("mug", 5)
	g := &gateway{}
	audit := payments.NewAuditLog(now)
	co := &Checkout{
		Sessions: sessions,
		Stock:    stock,
		Payments: payments.NewProcessor(g, audit),
		Region:   pricing.Region{Code: "QC", RatePPM: 149_750},
		Now:      now,
	}
	return &shop{checkout: co, gateway: g, audit: audit, token: token}
}

// @req R-CHECKOUT-ORDER
func TestPlaceOrder(t *testing.T) {
	s := newShop(t)
	var c Cart
	c.Add("mug", 1_000, 2)
	order, err := s.checkout.PlaceOrder(s.token, &c, nil, "order-1")
	if err != nil {
		t.Fatal(err)
	}
	if order.Quote.Total != 2_300 || order.Receipt.Amount != 2_300 {
		t.Fatalf("total %v, charged %v; want 23.00 for both", order.Quote.Total, order.Receipt.Amount)
	}
	if got := s.checkout.Stock.Available("mug"); got != 3 {
		t.Fatalf("mugs left = %d; want 3", got)
	}
	if _, err := s.checkout.PlaceOrder(s.token, &Cart{}, nil, "order-2"); !errors.Is(err, ErrEmptyCart) {
		t.Fatalf("empty cart: err = %v; want ErrEmptyCart", err)
	}
}

// @req R-CHECKOUT-SESSION
func TestPlaceOrderNeedsSession(t *testing.T) {
	s := newShop(t)
	var c Cart
	c.Add("mug", 1_000, 1)
	_, err := s.checkout.PlaceOrder("forged-token", &c, nil, "order-1")
	if !errors.Is(err, accounts.ErrNoSession) {
		t.Fatalf("unknown session: err = %v; want ErrNoSession", err)
	}
	if n := len(s.audit.Entries()); n != 0 {
		t.Fatalf("%d audit entries; want no charge", n)
	}
}

// @req R-STOCK-RELEASE
func TestPlaceOrderReleasesStockOnDecline(t *testing.T) {
	s := newShop(t)
	s.gateway.decline = true
	var c Cart
	c.Add("mug", 1_000, 4)
	_, err := s.checkout.PlaceOrder(s.token, &c, nil, "order-1")
	var decline *payments.DeclineError
	if !errors.As(err, &decline) {
		t.Fatalf("declined card: err = %v; want DeclineError", err)
	}
	if got := s.checkout.Stock.Available("mug"); got != 5 {
		t.Fatalf("mugs available after decline = %d; want 5", got)
	}
}
