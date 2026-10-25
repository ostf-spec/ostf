// SPDX-License-Identifier: Apache-2.0
package accounts

import (
	"bytes"
	"errors"
	"testing"
	"time"
)

func newSessions(t *testing.T) (*Sessions, *time.Time) {
	t.Helper()
	now := time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC)
	s := NewSessions(func() time.Time { return now })
	if _, err := s.Register("ana@example.com", "correct horse", false); err != nil {
		t.Fatal(err)
	}
	return s, &now
}

func TestLogin(t *testing.T) {
	s, _ := newSessions(t)
	if _, err := s.Login("ana@example.com", "wrong"); !errors.Is(err, ErrBadCredentials) {
		t.Fatalf("wrong password: err = %v; want ErrBadCredentials", err)
	}
	token, err := s.Login("ana@example.com", "correct horse")
	if err != nil || token == "" {
		t.Fatalf("right password: token %q, err %v", token, err)
	}
	if c := s.byEmail["ana@example.com"]; bytes.Contains(c.hash, []byte("correct horse")) || len(c.salt) == 0 {
		t.Fatal("stored credentials hold the password or no salt")
	}
}

// @req R-LOGIN-LOCKOUT
func TestLoginLockout(t *testing.T) {
	s, now := newSessions(t)
	for range MaxFailedLogins {
		s.Login("ana@example.com", "guess")
	}
	if _, err := s.Login("ana@example.com", "correct horse"); !errors.Is(err, ErrLocked) {
		t.Fatalf("right password while locked: err = %v; want ErrLocked", err)
	}
	*now = now.Add(LockoutDuration)
	if _, err := s.Login("ana@example.com", "correct horse"); err != nil {
		t.Fatalf("after the lockout: %v", err)
	}
}

// @req R-SESSION-EXPIRY
func TestSessionExpiry(t *testing.T) {
	s, now := newSessions(t)
	token, err := s.Login("ana@example.com", "correct horse")
	if err != nil {
		t.Fatal(err)
	}
	*now = now.Add(SessionIdle - time.Second)
	if _, err := s.Validate(token); err != nil {
		t.Fatalf("session used within the idle time: %v", err)
	}
	*now = now.Add(SessionIdle)
	if _, err := s.Validate(token); !errors.Is(err, ErrSessionExpired) {
		t.Fatalf("idle session: err = %v; want ErrSessionExpired", err)
	}
}
