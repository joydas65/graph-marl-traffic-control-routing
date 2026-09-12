# Thin B0 OD live binding V1 — implementation stopped at finalization contract

Date: 2026-09-06. Status: **BLOCKED_SCOPE_INCOMPATIBILITY**, not an experiment
outcome and not a failure of the previously accepted offline checkpoint.

## Checkpoint and bounded changes

Started with clean `main`/`origin/main` at
`c0be5ca5c0116179f901bd00410c74e581799c87`, tree
`3bf64d0607cd3e7b3ce446c145c92d178be4fb11`. Created only local branch
`feature/b0-od-live-binding-v1`; no commit, publication or live execution.

No production module, accepted interface, source-binding manifest, Contract V1,
Adapter V2, historical dependency or scientific rule was changed. In particular,
the synthetic-only origin contract remains unchanged. No partially operational
launcher was added. Changes are this note, one focused characterization test,
and the required concise progress-log entry.

## Precise incompatibility

The task permits accepted integration changes only for evidence origin and
specifically needed read-only getters, while requiring preservation of status
semantics and independent integrity FAIL precedence. A finalized-process/log
or output-identity contradiction cannot currently cross that boundary truthfully:

1. `integration.observe_run` collects its last controls/diagnostics before
   connection cleanup. `collector.finalize_output()` subsequently returns XML
   only. There is no validated terminal diagnostic/exit/output-identity field.
2. With no earlier failure, **every** exception from finalization becomes
   `EVIDENCE / TRIPINFO_FINALIZATION`. With otherwise consistent full-H data,
   this yields `INCONCLUSIVE`, even when the collector knows a positive
   integrity contradiction rather than simply missing output.
3. After a supported unchanged-clock step abort, the first `TECHNICAL` failure
   is preserved and a finalizer exception is not separately retained.
   `assess_run` can therefore remain `BLOCKED`, despite an independent terminal
   contradiction. Raising during `close` records a cleanup deficiency, not an
   independently classified integrity failure.
4. Returning valid XML while retaining the contradiction only in the collector
   loses it to run/pair validation. The strict FAILURE envelope can retain it in
   `raw_evidence`, but does not interpret that field; attaching the run and
   declaring `experiment_status=FAIL` contradicts recomputed `BLOCKED` and is
   rejected by the writer/readback contract.

The synthetic reproducer confirms all four paths through the actual integration,
accounting, pair qualification, and strict writer/readback. It does not claim a
real SUMO error was observed. A nonzero exit alone is **not** asserted to prove a
scientific integrity failure: the injected case also supplies an explicitly
known positive output-identity contradiction.

Relabeling the first failure, fabricating pre-close diagnostics, modifying XML
to manufacture an Adapter error, or relying on an unvalidated sidecar would not
satisfy the requested provenance and revalidation constraints. Using `run=None`
can retain uninterpreted raw evidence, but cannot provide the required run/pair
status propagation. Adding terminal semantics inside an origin field would
still be a status-contract change, not merely origin separation.

**Required new gate (proposal, not implemented):** authorize a narrowly versioned
terminal-finalization evidence contract and deterministic status reconciliation
through run assessment, pair/selection validation and writer/readback. It must
retain the first failure, raw XML and separate cleanup results; distinguish
positive contradictions, missing coverage and ambiguous operational outcomes;
and retain FAIL precedence without broad TECHNICAL-to-BLOCKED conversion. No
threshold, accounting, allocation, repeat or execution-budget change is needed
or proposed. Its exact schema and mappings require review before implementation.

## Version/API evidence collected before stopping

Read only the explicitly identified installed framework payload at
`/Library/Frameworks/EclipseSUMO.framework/EclipseSUMO/`.
`/Library/Frameworks/EclipseSUMO.framework/Versions/Current` points to `1.27.1/`; the installed
`share/sumo/tools/traci/constants.py` declares protocol 22. Intended executable
is `bin/sumo`, client is `share/sumo/tools/traci/`. These are static provenance,
not a runtime identity query or proof of installed-binary compatibility.

- Native lane allowed/disallowed getters derive complementary lists from one
  permission mask, not two independent mutable lists. A documented normalization
  with retained raw evidence still needs implementation and tests.
  [SUMO 1.27.1 Lane implementation](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/libsumo/Lane.cpp).
- Installed client text exposes `simulation.getOption` for effective options;
  `getPendingVehicles` means delayed insertion, not all future demand. Input
  hashes would come from actual launched files; contract labels would remain
  explicitly static. No observed-control mapping was implemented or validated.
- Versioned option definitions include `tripinfo-output.write-unfinished` and
  the distinct `tripinfo-output.write-undeparted`. Selecting flags must preserve
  original timestamps/sentinels and Adapter V2 rules, not normalize unknowns.
  [SUMO 1.27.1 option definitions](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/microsim/MSFrame.cpp).
- Error logs also receive warnings; mere log presence is not an error count.
  [SUMO 1.27.1 message handling](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/utils/common/MsgHandler.cpp).
- Installed `traci/main.py` allows a single attempt with `numRetries=0` but
  exposes no connection timeout argument. `connection.py` uses blocking socket
  connect/receive and `close(wait=True)` can call an unbounded process wait.
  A bounded owned-process/transport design remains unresolved, not declared
  impossible. A loopback client destination is not proof of server listening
  scope; a separately authorized live check must establish actual bind scope.

No simulator/client import, simulator binary invocation, simulator socket, installation,
private-source access or cloud operation was performed.

## Offline evidence and source identities

Commands use Python 3.12.14 with `-I -S -B` and the existing safety harness:

```text
python3 -I -S -B tests/test_od_live_binding_finalization_boundary.py
python3 -I -S -B tests/run_b0_od_integration_offline.py new
python3 -I -S -B tests/run_b0_od_integration_offline.py existing
```

| Surface | Tests passed | Subtests | Meaning |
| --- | ---: | ---: | --- |
| New boundary characterization | 7 | 4 | Confirms unsupported behavior, NOT binding acceptance |
| Accepted integration | 86 | 134 | Regression only |
| Existing B0/Adapter V2 | 153 | 175 | Regression only |

The new test SHA-256 is
`b75d800332163d9b4cd3c9bf7793b2195cec9aa6a8dac0e9ec0d1c795535a3b1`.
Accepted integration source identities remain:

```text
integration.py   aee3028c1e2fd6d8972955bbd5375cff083a1787f5ab26409182d28338a5de37
qualification.py 955c13ee956a929bce167eb6d61ea335967944596c7539959f55353c2fd3aec3
evidence.py      11b2995f5f161be2dff062a5d2c119fe396a954f2582e242e37de7576e5cb517
```

The new test deliberately sits outside both accepted discovery patterns; its
counts are separate, not added to existing suite totals. Temporary synthetic
writer files use the existing isolated output area and are cleaned up by the
test. All three runs had zero failures, errors, skips, collection errors or
forbidden-access attempts; the harness-checked source hashes stayed unchanged.
The integration suite took 248.39 seconds and retained the 56,900,339-byte full
synthetic fixture within the unchanged 64 MiB limit. In-memory compilation of
the new test and whitespace checks (including both untracked files) passed.
Contract V1 and Adapter V2 hashes still match their frozen identities; accepted
source/projection checks passed. The index is empty and only the three stated
files are uncommitted changes; HEAD, local main and origin/main remain at the
starting checkpoint.

## Readiness

`THIN_LIVE_BINDING_IMPLEMENTED=NO`; launch plan, observed-control mapping,
origin extension and native lifecycle acceptance are not validated. Existing
offline success cannot substitute for those missing surfaces.

`LIVE_PROCESS_STARTED=NO`, `SIMULATOR_SOCKET_OPENED=NO`,
`LIVE_INTEGRATION_VALIDATED=NO`, `OD_CALIBRATION_EXECUTED=NO`,
`SELECTED_CALIBRATED_OD_CONCENTRATION=NONE`,
`DISSERTATION_DELTA_REMAINS_UNSET=YES`, `READY_TO_RUN=NO`.

The requested eventual review/publication task is blocked until this contract
gate is authorized and resolved and the thin binding is actually implemented
and offline-validated. Neither that task nor live validation was started.
