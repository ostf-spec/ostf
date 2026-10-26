// SPDX-License-Identifier: Apache-2.0
package payments

import (
	"errors"
	"fmt"
	"testing"
	"time"

	"example.com/shop/pricing"
)

// fakeGateway records calls and declines when decline is set.
type fakeGateway struct {
	decline string
	charges int
	refunds map[string]pricing.Money // by transaction
}

func (g *fakeGateway) Charge(account string, amount pricing.Money) (string, error) {
	if g.decline != "" {
		return "", &DeclineError{Reason: g.decline}
	}
	g.charges++
	return fmt.Sprintf("txn-%d", g.charges), nil
}

func (g *fakeGateway) Refund(txn string, amount pricing.Money) error {
	if g.refunds == nil {
		g.refunds = map[string]pricing.Money{}
	}
	g.refunds[txn] += amount
	return nil
}

var testTime = time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC)

func newProcessor() (*Processor, *fakeGateway, *AuditLog) {
	g := &fakeGateway{}
	log := NewAuditLog(func() time.Time { return testTime })
	return NewProcessor(g, log), g, log
}

func TestValidateAmount(t *testing.T) {
	for _, amount := range []pricing.Money{0, -1, MaxCharge + 1} {
		if err := ValidateAmount(amount); !errors.Is(err, ErrAmount) {
			t.Errorf("ValidateAmount(%v) = %v; want ErrAmount", amount, err)
		}
	}
	for _, amount := range []pricing.Money{1, MaxCharge} {
		if err := ValidateAmount(amount); err != nil {
			t.Errorf("ValidateAmount(%v) = %v; want nil", amount, err)
		}
	}
}

// @req R-IDEMPOTENT-CHARGE
func TestChargeRetry(t *testing.T) {
	p, g, _ := newProcessor()
	first, err := p.Charge("order-1", "acct-1", 2_500)
	if err != nil {
		t.Fatal(err)
	}
	second, err := p.Charge("order-1", "acct-1", 2_500)
	if err != nil {
		t.Fatal(err)
	}
	if g.charges != 1 || first != second {
		t.Fatalf("retry: %d gateway charges, receipts %v and %v; want 1 charge, same receipt", g.charges, first, second)
	}
}

func TestChargeKeyReuse(t *testing.T) {
	p, _, _ := newProcessor()
	if _, err := p.Charge("order-1", "acct-1", 2_500); err != nil {
		t.Fatal(err)
	}
	if _, err := p.Charge("order-1", "acct-1", 9_900); !errors.Is(err, ErrKeyReused) {
		t.Fatalf("same key, other amount: err = %v; want ErrKeyReused", err)
	}
}

// @req R-CHARGE-DECLINE
func TestChargeDecline(t *testing.T) {
	p, g, _ := newProcessor()
	g.decline = "insufficient funds"
	_, err := p.Charge("order-1", "acct-1", 2_500)
	var decline *DeclineError
	if !errors.As(err, &decline) || decline.Reason != "insufficient funds" {
		t.Fatalf("declined charge: err = %v; want DeclineError with the reason", err)
	}
	g.decline = ""
	if _, err := p.Charge("order-1", "acct-1", 2_500); err != nil {
		t.Fatalf("retry after decline: %v", err)
	}
}

func TestChargeAudited(t *testing.T) {
	p, _, log := newProcessor()
	r, err := p.Charge("order-1", "acct-1", 2_500)
	if err != nil {
		t.Fatal(err)
	}
	want := []Entry{{Time: testTime, Account: "acct-1", Action: "charge", Amount: 2_500, Ref: r.ID}}
	if got := log.Entries(); len(got) != 1 || got[0] != want[0] {
		t.Fatalf("audit = %+v; want %+v", got, want)
	}
}
