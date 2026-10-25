// SPDX-License-Identifier: Apache-2.0

// Package inventory tracks the stock on hand and holds it for orders in
// progress.
package inventory

import (
	"errors"
	"fmt"
	"maps"
	"sync"
	"time"
)

// HoldDuration is how long a reservation holds stock before it expires.
const HoldDuration = 15 * time.Minute

var (
	// ErrInsufficient is returned when a reservation asks for more than is available.
	ErrInsufficient = errors.New("inventory: insufficient stock")
	// ErrNoReservation is returned when confirming an unknown or expired reservation.
	ErrNoReservation = errors.New("inventory: no such reservation")
)

// Reservation holds quantities of several SKUs until it expires.
type Reservation struct {
	ID      string
	Items   map[string]int
	Expires time.Time
}

// Stock is the stock on hand per SKU and the reservations against it. It is
// safe for concurrent use.
type Stock struct {
	mu     sync.Mutex
	now    func() time.Time
	onHand map[string]int
	holds  map[string]Reservation
	seq    int
}

// NewStock returns empty stock that reads the current time from now.
func NewStock(now func() time.Time) *Stock {
	return &Stock{now: now, onHand: map[string]int{}, holds: map[string]Reservation{}}
}

// Receive adds qty units of sku to the stock on hand.
func (s *Stock) Receive(sku string, qty int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.onHand[sku] += qty
}

// Available returns the units of sku that no unexpired reservation holds.
func (s *Stock) Available(sku string) int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.available(sku)
}

// available is Available for a caller that holds s.mu.
// @req D-RESERVATION-HOLD
func (s *Stock) available(sku string) int {
	n := s.onHand[sku]
	now := s.now()
	for _, h := range s.holds {
		if now.Before(h.Expires) {
			n -= h.Items[sku]
		}
	}
	return n
}

// Reserve holds every quantity in items for HoldDuration, or holds nothing
// when any SKU is short.
func (s *Stock) Reserve(items map[string]int) (Reservation, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for sku, qty := range items {
		if qty > s.available(sku) {
			return Reservation{}, fmt.Errorf("%w: %s", ErrInsufficient, sku)
		}
	}
	s.seq++
	r := Reservation{
		ID:      fmt.Sprintf("hold-%d", s.seq),
		Items:   maps.Clone(items),
		Expires: s.now().Add(HoldDuration),
	}
	s.holds[r.ID] = r
	return r, nil
}

// Release returns the stock held by reservation id. Releasing an unknown or
// expired reservation does nothing.
func (s *Stock) Release(id string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.holds, id)
}

// Confirm turns reservation id into a sale: its quantities leave the stock
// on hand. An expired reservation cannot be confirmed.
func (s *Stock) Confirm(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	h, ok := s.holds[id]
	delete(s.holds, id)
	if !ok || !s.now().Before(h.Expires) {
		return fmt.Errorf("%w: %s", ErrNoReservation, id)
	}
	for sku, qty := range h.Items {
		s.onHand[sku] -= qty
	}
	return nil
}
