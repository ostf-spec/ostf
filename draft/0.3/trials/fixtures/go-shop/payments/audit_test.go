// SPDX-License-Identifier: Apache-2.0
package payments

import (
	"testing"
	"time"
)

func TestAuditEntriesAreCopies(t *testing.T) {
	log := NewAuditLog(func() time.Time { return testTime })
	log.Append(Entry{Account: "acct-1", Action: "charge", Amount: 100, Ref: "rcpt-1"})
	got := log.Entries()
	got[0].Amount = 1
	if again := log.Entries(); again[0].Amount != 100 {
		t.Fatalf("changing a returned entry changed the log: %+v", again[0])
	}
}

func TestAuditStampsTime(t *testing.T) {
	log := NewAuditLog(func() time.Time { return testTime })
	log.Append(Entry{Account: "acct-1", Action: "refund", Amount: 100, Ref: "rcpt-1", Time: time.Unix(0, 0)})
	if got := log.Entries()[0].Time; !got.Equal(testTime) {
		t.Fatalf("entry time = %v; want the log's clock, %v", got, testTime)
	}
}
