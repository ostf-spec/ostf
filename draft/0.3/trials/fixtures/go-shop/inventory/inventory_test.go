// SPDX-License-Identifier: Apache-2.0
package inventory

import (
	"errors"
	"testing"
	"time"
)

// clock is a test clock that moves only when told to.
type clock struct{ t time.Time }

func (c *clock) now() time.Time { return c.t }

func newStock() (*Stock, *clock) {
	c := &clock{t: time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC)}
	s := NewStock(c.now)
	s.Receive("mug", 3)
	s.Receive("tea", 1)
	return s, c
}

// @req R-STOCK-RESERVE
func TestReserveAllOrNothing(t *testing.T) {
	s, _ := newStock()
	_, err := s.Reserve(map[string]int{"mug": 2, "tea": 2})
	if !errors.Is(err, ErrInsufficient) {
		t.Fatalf("short reservation: err = %v; want ErrInsufficient", err)
	}
	if got := s.Available("mug"); got != 3 {
		t.Fatalf("after failed reservation, mug available = %d; want 3", got)
	}
	if _, err := s.Reserve(map[string]int{"mug": 2, "tea": 1}); err != nil {
		t.Fatal(err)
	}
	if got := s.Available("mug"); got != 1 {
		t.Fatalf("mug available = %d; want 1", got)
	}
}

func TestRelease(t *testing.T) {
	s, _ := newStock()
	r, err := s.Reserve(map[string]int{"mug": 3})
	if err != nil {
		t.Fatal(err)
	}
	s.Release(r.ID)
	if got := s.Available("mug"); got != 3 {
		t.Fatalf("after release, mug available = %d; want 3", got)
	}
}

// @req R-STOCK-EXPIRY
func TestReservationExpires(t *testing.T) {
	s, c := newStock()
	r, err := s.Reserve(map[string]int{"mug": 3})
	if err != nil {
		t.Fatal(err)
	}
	c.t = c.t.Add(HoldDuration)
	if got := s.Available("mug"); got != 3 {
		t.Fatalf("after expiry, mug available = %d; want 3", got)
	}
	if err := s.Confirm(r.ID); !errors.Is(err, ErrNoReservation) {
		t.Fatalf("confirm expired: err = %v; want ErrNoReservation", err)
	}
}

func TestConfirm(t *testing.T) {
	s, _ := newStock()
	r, err := s.Reserve(map[string]int{"mug": 2})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.Confirm(r.ID); err != nil {
		t.Fatal(err)
	}
	if got := s.Available("mug"); got != 1 {
		t.Fatalf("after confirm, mug available = %d; want 1", got)
	}
	if err := s.Confirm(r.ID); !errors.Is(err, ErrNoReservation) {
		t.Fatalf("second confirm: err = %v; want ErrNoReservation", err)
	}
}
