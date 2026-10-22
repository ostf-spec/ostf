<!-- SPDX-License-Identifier: CC-BY-4.0 -->
## What changes

Describe the problem and the proposed resolution. Link an issue when one exists.

## Draft impact

- Affected `OSTF-` IDs, schemas, annexes and fixtures:
- Wire compatibility and claim boundary:
- Documentation or migration impact:

## Checks

- [ ] `python3 conformance/run.py`
- [ ] `go test ./...` and `go vet ./...`
- [ ] `cd examples/minimal && go test ./...` if the worked example changed
- [ ] New or changed behavior has a fixed positive and negative case, where applicable
- [ ] License and third-party attribution are clear
