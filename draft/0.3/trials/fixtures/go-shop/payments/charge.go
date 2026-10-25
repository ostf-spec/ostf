// SPDX-License-Identifier: Apache-2.0

// Package payments charges customers through a card gateway, refunds them,
// and records every movement of money in an audit log.
package payments

import (
	"errors"
	"fmt"
	"sync"

	"example.com/shop/pricing"
)

// MaxCharge is the largest amount that a single charge may take: 10,000.00.
const MaxCharge pricing.Money = 1_000_000

var (
	// ErrAmount is returned for a charge of zero, less, or more than MaxCharge.
	ErrAmount = errors.New("payments: charge must be more than 0.00 and at most 10,000.00")
	// ErrKeyReused is returned when an idempotency key comes back with another charge.
	ErrKeyReused = errors.New("payments: idempotency key reused for a different charge")
)

// Gateway is the card processor. Charge returns the gateway's transaction
// ID; Refund sends money back to the card of that transaction.
type Gateway interface {
	Charge(account string, amount pricing.Money) (txn string, err error)
	Refund(txn string, amount pricing.Money) error
}

// DeclineError is returned by a Gateway that declines a charge.
type DeclineError struct {
	Reason string
}

func (e *DeclineError) Error() string { return "payments: charge declined: " + e.Reason }

// Receipt records a successful charge.
type Receipt struct {
	ID      string
	Account string
	Amount  pricing.Money
	Txn     string
}

// Processor charges through a gateway and keeps the receipt of each
// successful charge under its idempotency key. It is safe for concurrent use.
type Processor struct {
	gateway Gateway
	audit   *AuditLog
	mu      sync.Mutex
	byKey   map[string]Receipt
	byID    map[string]Receipt
}

// NewProcessor returns a Processor that charges through g and audits to log.
func NewProcessor(g Gateway, log *AuditLog) *Processor {
	return &Processor{gateway: g, audit: log, byKey: map[string]Receipt{}, byID: map[string]Receipt{}}
}

// ValidateAmount rejects a charge that is zero, negative or above MaxCharge.
func ValidateAmount(amount pricing.Money) error {
	if amount <= 0 || amount > MaxCharge {
		return fmt.Errorf("%w: got %v", ErrAmount, amount)
	}
	return nil
}

// Charge charges amount to account under the idempotency key. A retry with
// the same key returns the first receipt without calling the gateway again.
// A declined charge is not remembered, so the customer can retry it.
// @req R-IDEMPOTENT-CHARGE
func (p *Processor) Charge(key, account string, amount pricing.Money) (Receipt, error) {
	if err := ValidateAmount(amount); err != nil {
		return Receipt{}, err
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	if r, ok := p.byKey[key]; ok {
		if r.Account != account || r.Amount != amount {
			return Receipt{}, ErrKeyReused
		}
		return r, nil
	}
	txn, err := p.gateway.Charge(account, amount)
	if err != nil {
		return Receipt{}, err
	}
	r := Receipt{ID: "rcpt-" + key, Account: account, Amount: amount, Txn: txn}
	p.byKey[key] = r
	p.byID[r.ID] = r
	p.audit.Append(Entry{Account: account, Action: "charge", Amount: amount, Ref: r.ID})
	return r, nil
}

// receipt returns the receipt with the given ID, which names the gateway
// transaction that a refund must go back to.
// @req R-REFUND-ORIGINAL
func (p *Processor) receipt(id string) (Receipt, bool) {
	p.mu.Lock()
	defer p.mu.Unlock()
	r, ok := p.byID[id]
	return r, ok
}
