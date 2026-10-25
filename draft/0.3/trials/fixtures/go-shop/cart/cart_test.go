// SPDX-License-Identifier: Apache-2.0
package cart

import (
	"errors"
	"slices"
	"testing"
)

// @req R-CART-ADD
func TestAddMergesLines(t *testing.T) {
	var c Cart
	if err := c.Add("mug", 1_200, 1); err != nil {
		t.Fatal(err)
	}
	if err := c.Add("mug", 1_200, 2); err != nil {
		t.Fatal(err)
	}
	want := []Line{{SKU: "mug", UnitPrice: 1_200, Quantity: 3}}
	if !slices.Equal(c.lines, want) {
		t.Fatalf("lines = %v; want %v", c.lines, want)
	}
}

func TestAddRejectsBadQuantity(t *testing.T) {
	var c Cart
	if err := c.Add("mug", 1_200, 0); !errors.Is(err, ErrQuantity) {
		t.Fatalf("quantity 0: err = %v; want ErrQuantity", err)
	}
	if err := c.Add("mug", 1_200, 98); err != nil {
		t.Fatal(err)
	}
	if err := c.Add("mug", 1_200, 2); !errors.Is(err, ErrQuantity) {
		t.Fatalf("quantity 100: err = %v; want ErrQuantity", err)
	}
	if c.lines[0].Quantity != 98 {
		t.Fatalf("after a rejected add, quantity = %d; want 98", c.lines[0].Quantity)
	}
}

func TestRemove(t *testing.T) {
	var c Cart
	c.Add("mug", 1_200, 1)
	c.Add("tea", 800, 1)
	c.Remove("mug")
	c.Remove("kettle")
	if len(c.lines) != 1 || c.lines[0].SKU != "tea" {
		t.Fatalf("lines = %v; want only tea", c.lines)
	}
}

func TestSubtotal(t *testing.T) {
	var c Cart
	c.Add("mug", 1_200, 2)
	c.Add("tea", 850, 3)
	if got := c.Subtotal(); got != 4_950 {
		t.Fatalf("subtotal = %v; want 49.50", got)
	}
}
