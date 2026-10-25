// SPDX-License-Identifier: Apache-2.0
package payments

import (
	"errors"
	"sync"
	"time"

	"example.com/shop/pricing"
)

// DailyRefundLimit is the refund total per account and UTC day above which a
// refund needs a second approval: 500.00.
const DailyRefundLimit pricing.Money = 50_000

var (
	// ErrRefundTooLarge is returned for a refund above what is left of its charge.
	ErrRefundTooLarge = errors.New("payments: refund exceeds what is left of the charge")
	// ErrNeedsApproval is returned for a refund above the daily limit without a second approver.
	ErrNeedsApproval = errors.New("payments: refund above the daily limit needs a second approval")
	// ErrUnknownReceipt is returned for a refund of a charge that does not exist.
	ErrUnknownReceipt = errors.New("payments: unknown receipt")
)

// RefundRequest asks to refund Amount of the charge with ReceiptID.
type RefundRequest struct {
	ReceiptID  string
	Amount     pricing.Money
	ApprovedBy string // the second approver, or empty
}

// Refunder refunds earlier charges within the refund limit. It keeps what
// was refunded of each charge and of each account per UTC day.
type Refunder struct {
	processor *Processor
	now       func() time.Time
	mu        sync.Mutex
	refunded  map[string]pricing.Money // by receipt ID
	daily     map[string]pricing.Money // by dayKey
}

// NewRefunder returns a Refunder for the charges that p made.
func NewRefunder(p *Processor, now func() time.Time) *Refunder {
	return &Refunder{processor: p, now: now, refunded: map[string]pricing.Money{}, daily: map[string]pricing.Money{}}
}

// CheckRefundLimit rejects a refund that is not positive or exceeds what is
// left of its charge, and one that takes the account's refunds for the day
// above DailyRefundLimit without a second approval.
func CheckRefundLimit(amount, leftOnCharge, refundedToday pricing.Money, approved bool) error {
	if amount <= 0 || amount > leftOnCharge {
		return ErrRefundTooLarge
	}
	if refundedToday+amount > DailyRefundLimit && !approved {
		return ErrNeedsApproval
	}
	return nil
}

// Refund refunds req.Amount of an earlier charge to the card that was
// charged, and records it in the audit log.
// @req R-REFUND-ORIGINAL
func (r *Refunder) Refund(req RefundRequest) error {
	rcpt, ok := r.processor.receipt(req.ReceiptID)
	if !ok {
		return ErrUnknownReceipt
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	day := dayKey(rcpt.Account, r.now())
	left := rcpt.Amount - r.refunded[rcpt.ID]
	if err := CheckRefundLimit(req.Amount, left, r.daily[day], req.ApprovedBy != ""); err != nil {
		return err
	}
	if err := r.processor.gateway.Refund(rcpt.Txn, req.Amount); err != nil {
		return err
	}
	r.refunded[rcpt.ID] += req.Amount
	r.daily[day] += req.Amount
	r.processor.audit.Append(Entry{Account: rcpt.Account, Action: "refund", Amount: req.Amount, Ref: rcpt.ID})
	return nil
}

// dayKey keys the daily refund total by account and UTC calendar day.
// @req D-REFUND-LEDGER
func dayKey(account string, t time.Time) string {
	return account + "/" + t.UTC().Format(time.DateOnly)
}
