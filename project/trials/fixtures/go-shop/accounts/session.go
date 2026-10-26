// SPDX-License-Identifier: Apache-2.0

// Package accounts registers customers, logs them in and keeps their sessions.
package accounts

import (
	"crypto/pbkdf2"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"errors"
	"fmt"
	"sync"
	"time"
)

const (
	// MaxFailedLogins is the number of consecutive failed logins that locks an account.
	MaxFailedLogins = 5
	// LockoutDuration is how long a locked account refuses logins.
	LockoutDuration = 15 * time.Minute
	// SessionIdle is how long a session lasts without use.
	SessionIdle = 30 * time.Minute

	hashIterations = 100_000
)

var (
	ErrEmailTaken     = errors.New("accounts: email already registered")
	ErrBadCredentials = errors.New("accounts: wrong email or password")
	ErrLocked         = errors.New("accounts: account locked after too many failed logins")
	ErrNoSession      = errors.New("accounts: no such session")
	ErrSessionExpired = errors.New("accounts: session expired")
)

// Account is a registered customer.
type Account struct {
	ID        string
	Email     string
	TaxExempt bool
}

type credentials struct {
	account     Account
	salt, hash  []byte
	failed      int
	lockedUntil time.Time
}

type session struct {
	account  Account
	lastUsed time.Time
}

// Sessions holds accounts and their login sessions. It is safe for
// concurrent use.
type Sessions struct {
	mu       sync.Mutex
	now      func() time.Time
	byEmail  map[string]*credentials
	sessions map[string]*session
}

// NewSessions returns an empty store that reads the current time from now.
func NewSessions(now func() time.Time) *Sessions {
	return &Sessions{now: now, byEmail: map[string]*credentials{}, sessions: map[string]*session{}}
}

// Register creates an account for email with a salted hash of password.
func (s *Sessions) Register(email, password string, taxExempt bool) (Account, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.byEmail[email]; ok {
		return Account{}, ErrEmailTaken
	}
	salt := make([]byte, 16)
	rand.Read(salt)
	hash, err := hashPassword(password, salt)
	if err != nil {
		return Account{}, err
	}
	acct := Account{ID: fmt.Sprintf("acct-%d", len(s.byEmail)+1), Email: email, TaxExempt: taxExempt}
	s.byEmail[email] = &credentials{account: acct, salt: salt, hash: hash}
	return acct, nil
}

// hashPassword derives the stored hash of password with PBKDF2-SHA256.
// @req R-PASSWORD-HASH
func hashPassword(password string, salt []byte) ([]byte, error) {
	return pbkdf2.Key(sha256.New, password, salt, hashIterations, 32)
}

// Login checks email and password and returns a new session token. After
// MaxFailedLogins consecutive failures the account is locked for
// LockoutDuration, and even the right password is refused until then.
func (s *Sessions) Login(email, password string) (string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	c, ok := s.byEmail[email]
	if !ok {
		return "", ErrBadCredentials
	}
	now := s.now()
	if now.Before(c.lockedUntil) {
		return "", ErrLocked
	}
	hash, err := hashPassword(password, c.salt)
	if err != nil {
		return "", err
	}
	if subtle.ConstantTimeCompare(hash, c.hash) != 1 {
		c.failed++
		if c.failed >= MaxFailedLogins {
			c.failed = 0
			c.lockedUntil = now.Add(LockoutDuration)
		}
		return "", ErrBadCredentials
	}
	c.failed = 0
	token := newToken()
	s.sessions[token] = &session{account: c.account, lastUsed: now}
	return token, nil
}

// Validate returns the account that holds the session token and extends the
// session. A session unused for SessionIdle has expired.
// @req R-SESSION-EXPIRY
func (s *Sessions) Validate(token string) (Account, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.sessions[token]
	if !ok {
		return Account{}, ErrNoSession
	}
	now := s.now()
	if now.Sub(sess.lastUsed) >= SessionIdle {
		delete(s.sessions, token)
		return Account{}, ErrSessionExpired
	}
	sess.lastUsed = now
	return sess.account, nil
}

// newToken returns a random session token.
func newToken() string {
	return rand.Text()
}
