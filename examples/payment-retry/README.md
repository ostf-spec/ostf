<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# A payment retry, traced from requirement to test

A customer retries a charge request after a timeout. The requirement says a repeated idempotency key must return the first result without a second charge. In this small Go service, `Service.Charge` stores the result of the first successful gateway call, and `TestSameKey` checks that a retry calls the gateway only once.

`R-PAY-RETRY` is the stable OSTF requirement ID, not a Git commit or function hash. The customer's idempotency key is a separate input that controls payment retry behavior; it has no OSTF identity role.

- [trace.yaml](trace.yaml) declares `R-PAY-RETRY` and links it to the implementing method and regression test.
- [charge.go](pay/charge.go) and [retry_test.go](pay/retry_test.go) are the source tree that the anchors name.
- [trace.lock](trace.lock) contains the two endpoint stamps from a recheck of these exact bytes.
- [logs/retry-example.log](logs/retry-example.log) and [otel/retry-trace.json](otel/retry-trace.json) are synthetic references. The latter uses OTLP JSON shape. These files show the new `logs` and `otel` fields without claiming that this test produced an OpenTelemetry trace or retained execution evidence.
- `x-ticket: PAY-123` is an illustrative custom key. OSTF preserves `x-` values without assigning them standard meaning or including them in link freshness.

Run the test from this directory:

```sh
go test ./...
```

After running `python3 conformance/run.py` at the OSTF repository root, analyze the example:

```sh
.venv/bin/python conformance/reader.py examples/payment-retry
```

The current tree reports two valid links. If `Service.Charge` changes its signature, the implementing link becomes suspect under the `go1` fingerprint rule until someone rechecks the relationship and a tool writes a new stamp. A valid stamp is a freshness statement, not proof that the test ran or that the payment behavior is correct.

The in-memory map keeps this example small. A real payment service needs durable idempotency across restarts and processes, transaction handling and a gateway contract. This source illustrates traceability, not a production payment implementation.
