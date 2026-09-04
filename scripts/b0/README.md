# B0 deterministic SUMO substrate

This directory publishes the public-safe source and provenance package for the
validated `B0_GRID_3X3_V1` fixed-time, fixed-route substrate. The corresponding
experiment record is [`EXP-B0-000`](../../docs/experiments/EXP-B0-000.md).

## Source roles

| File | Role | SHA-256 |
|---|---|---|
| `run_b0.py` | Byte-exact source executed for the frozen B0 run | `d4286193089a8062ae16e51e3dbaf8f26df6be11d43399d6fd998941b275ccab` |
| `reference/run_b0_exposure_diagnostic.executed.py` | Byte-exact source executed for the exposure diagnostic | `dfe718d6ea28fc188072f596f935665c8299ad7148b20bef11b4d4a0482c5128` |
| `exposure_observer.py` | Validated reusable read-only exposure observer | `dd582ab3011d3077c1ad1f63b95f26708813bf0628dcdee4bebda4c054a68d57` |
| `validate_inputs.py` | Frozen static input validator | `1676c3fbbe84acc6f94943a8187424e2e2bc6b0fa05beecd14611342a188af5b` |
| `generate_demand.py` | Frozen deterministic 1X demand generator | `0802a05e7c542fe2e35ecd83a205a421ba1048aabbdd0e40495b5a827012ddf3` |

The two executed runners preserve their historical repository revision,
evidence topology, and write-once lifecycle checks. They are provenance
snapshots, not supported entry points at the current repository revision. They
have not been rewritten to appear reusable. A separately versioned public
harness may adapt them in a later task.

## Public artifacts

- Frozen inputs and their public path-relative hash map are under
  [`configs/b0/b0-grid-3x3-v1`](../../configs/b0/b0-grid-3x3-v1/).
- Compact validation and diagnostic results are under
  [`results/b0/b0-grid-3x3-v1/seed-20260904`](../../results/b0/b0-grid-3x3-v1/seed-20260904/).
- The exact validated observer-test source is archived at
  [`tests/reference/b0_exposure_observer_v1.py`](../../tests/reference/b0_exposure_observer_v1.py).
- The active offline test changes only loading scaffolding and preserves the
  validated test methods and assertions.

Raw traces, simulator logs, XML outputs, vehicle ledgers, event streams,
failed-attempt records, and machine-specific environment receipts remain in
ignored local evidence and are not published.

## Claim boundary

This package validates deterministic simulator measurement, input integrity,
event lifecycle observation, and lane-compliance instrumentation. The 1X
disruption remains `TOO_WEAK`. No RL or dissertation treatment was implemented
or evaluated.

The inherited upstream repository has no declared licence. This publication
does not add a repository-wide licence or assert new rights over inherited
`TLCS` code.
