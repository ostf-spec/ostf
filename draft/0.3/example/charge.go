// SPDX-License-Identifier: Apache-2.0
package payments

// Receipt is the result of a charge.
type Receipt struct {
	ID     string
	Amount int
}

// Gateway charges a card. It is a function so that tests can count calls.
type Gateway func(amount int) Receipt

// Service charges cards and remembers the first receipt for each idempotency key.
type Service struct {
	gateway  Gateway
	receipts map[string]Receipt
}

// NewService returns a Service that charges through gateway.
func NewService(gateway Gateway) *Service {
	return &Service{gateway: gateway, receipts: map[string]Receipt{}}
}

// Charge returns the first receipt recorded for key, calling the gateway only once.
// @req PAY-123
func (s *Service) Charge(key string, amount int) Receipt {
	if receipt, ok := s.receipts[key]; ok {
		return receipt
	}
	receipt := s.gateway(amount)
	s.receipts[key] = receipt
	return receipt
}
