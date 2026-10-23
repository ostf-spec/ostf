// SPDX-License-Identifier: Apache-2.0
package pay

import (
	"context"
	"testing"
)

type fakeGateway struct{ calls int }

func (g *fakeGateway) Charge(_ context.Context, amountCents int64) (Receipt, error) {
	g.calls++
	return Receipt{ID: "charge-1", AmountCents: amountCents}, nil
}

func TestSameKey(t *testing.T) {
	gateway := &fakeGateway{}
	service := NewService(gateway)
	first, err := service.Charge(context.Background(), "request-42", 2500)
	if err != nil {
		t.Fatal(err)
	}
	retry, err := service.Charge(context.Background(), "request-42", 2500)
	if err != nil {
		t.Fatal(err)
	}
	if retry != first || gateway.calls != 1 {
		t.Fatalf("retry = %+v, first = %+v, gateway calls = %d", retry, first, gateway.calls)
	}
}
