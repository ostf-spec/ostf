<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# A minimal OSTF repository

This is a complete small source tree drawn from the `repository-valid` conformance case. It demonstrates one requirement, one implementing Go function, one verifying Go test and two recorded link stamps.

- [trace.yaml](trace.yaml) declares `R-ADD` and its code and test anchors. The paths are relative to this repository's root.
- [math.go](math.go) defines `Add`; [math_test.go](math_test.go) defines `TestAdd`.
- [trace.lock](trace.lock) records sample fingerprints for each link. Each line names its source anchor, link type, target item and endpoint hashes. `f1` fingerprints the requirement's meaning; `go1` fingerprints Go tokens.

Run the Go test from this directory:

```sh
go test ./...
```

After running `python3 conformance/run.py` at the OSTF repository root, analyze this tree:

```sh
.venv/bin/python conformance/reader.py examples/minimal
```

The analyzer reports two `valid` links and no errors for these exact bytes. If you change the requirement text or a counted code fingerprint, the stored stamp no longer matches and the link becomes `suspect`. A valid stamp says only that its recorded inputs match; it does not say the test passed, the implementation is correct or a person reviewed this sample. Stamping again is a tool action after a person or process rechecks the relationship.

The example is deliberately small. The [Core draft](../../draft/core.md) defines the full data contract, and the [support map](../../draft/support.md) limits what the current prototype can check.
