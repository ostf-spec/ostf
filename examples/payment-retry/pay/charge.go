// SPDX-License-Identifier: Apache-2.0
package pay

import (
	"context"
	"errors"
	"sync"
)

// Receipt is the result returned by the payment gateway.
type Receipt struct {
	ID          string
	AmountCents int64
}

// Gateway performs the external charge.
type Gateway interface {
	Charge(context.Context, int64) (Receipt, error)
}

// Service remembers successful charges by idempotency key within this process.
type Service struct {
	mu       sync.Mutex
	gateway  Gateway
	receipts map[string]Receipt
}

func NewService(gateway Gateway) *Service {
	return &Service{gateway: gateway, receipts: make(map[string]Receipt)}
}

// Charge returns the original receipt when a request repeats the same key.
func (s *Service) Charge(ctx context.Context, key string, amountCents int64) (Receipt, error) {
	if key == "" || amountCents <= 0 {
		return Receipt{}, errors.New("a key and positive amount are required")
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	if receipt, ok := s.receipts[key]; ok {
		if receipt.AmountCents != amountCents {
			return Receipt{}, errors.New("a key cannot be reused for another amount")
		}
		return receipt, nil
	}

	receipt, err := s.gateway.Charge(ctx, amountCents)
	if err != nil {
		return Receipt{}, err
	}
	s.receipts[key] = receipt
	return receipt, nil
}
