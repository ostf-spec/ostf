// SPDX-License-Identifier: Apache-2.0
package payments

import (
	"slices"
	"sync"
	"time"

	"example.com/shop/pricing"
)

// Entry is one audit record of money moving.
type Entry struct {
	Time    time.Time
	Account string
	Action  string // "charge" or "refund"
	Amount  pricing.Money
	Ref     string // the receipt ID
}

// AuditLog is an append-only record of charges and refunds. It has no way
// to change or remove an entry. It is safe for concurrent use.
type AuditLog struct {
	mu      sync.Mutex
	now     func() time.Time
	entries []Entry
}

// NewAuditLog returns an empty log that stamps entries with the time from now.
func NewAuditLog(now func() time.Time) *AuditLog {
	return &AuditLog{now: now}
}

// Append stamps e with the current time and adds it to the end of the log.
func (l *AuditLog) Append(e Entry) {
	l.mu.Lock()
	defer l.mu.Unlock()
	e.Time = l.now()
	l.entries = append(l.entries, e)
}

// Entries returns a copy of the log, oldest entry first.
func (l *AuditLog) Entries() []Entry {
	l.mu.Lock()
	defer l.mu.Unlock()
	return slices.Clone(l.entries)
}
