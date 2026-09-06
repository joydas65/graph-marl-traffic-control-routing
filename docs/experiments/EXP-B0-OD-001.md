# EXP-B0-OD-001: fixed-3X OD protocol and corrected V2 adapter

Publication checkpoint: **5 September 2026**. Pre-run protocol and offline
implementation evidence only; no OD-concentration simulation has occurred.

## Research question and fixed controls

At fixed total demand and departure times, does concentrating existing OD
assignments through the selected disruption direction produce a measurable but
non-catastrophic fixed-time baseline disturbance?

The [validated B0 substrate](EXP-B0-000.md) remains distinct from scenario
sensitivity: original 1X was `TOO_WEAK`, and [uniform 2X–5X calibration](EXP-B0-CAL-001.md)
returned `NO_QUALIFYING_DEMAND_LEVEL`. Fixed 3X means **540 scheduled trips**, not
a selected calibrated scenario. No treatment, RL, routing, graph-method benefit
or central-hypothesis result is established. Candidate N remains parked.

The byte-exact [Scientific Contract V1](../../configs/b0/od-concentration-v1/calibration-contract.json)
is authoritative for the design. Its preimplementation status, validation and
next-task fields record the original design freeze, not current implementation
status; they are preserved rather than retrospectively rewritten. This note
records the subsequent V2 implementation checkpoint. Neither the narrowed scope
nor the ladder is represented as faculty-approved.

Retain the exact public `B0_GRID_3X3_V1` network, twelve route geometries, fixed
68-second signal programs, deterministic passenger attributes, one-second steps,
540 departures in `[0,900)`, and cutoff H=1500. D0 restricts passenger access to
`A1B1_0` during `[300,600)`, with `A1B1_1` surviving; N0 does not restrict it.
No rerouting or signal-policy intervention is permitted. Lane loss is not an
asserted exact physical capacity fraction. Contract source hashes bind the
unchanged inputs and public dependencies.

| Level | Trips on `row1_east` | Share of 540 | Target trips in each 60-second block |
|---|---:|---:|---:|
| C1 | 90 | 1/6 | 6 |
| C2 | 135 | 1/4 | 9 |
| C3 | 180 | 1/3 | 12 |
| C4 | 270 | 1/2 | 18 |

Use fifteen blocks of 36 slots: ID `veh_{36*b+k:04d}` and departure
`60*b + floor(5*k/3)`. For each seed, exactly fifteen fresh local-RNG shuffles
are reused across levels. Target sets are nested; the other eleven routes use
the frozen continuous cyclic allocation, without resetting between blocks.
Every route remains represented in every block. N0/D0 share identical input
bytes within each seed/level; across levels, equal IDs do **not** imply identical
OD populations. Planned target departures are not observed event-period entries.

Demand-assignment seeds are `20260904`, `20260905`, `20260906`; the simulator seed
stays `20260904`. The entire `A1B1/B1A1` corridor is calibration-seen, not eligible
for headline held-out-location evaluation. These calibration seeds are excluded
from final confirmatory treatment estimates absent later preregistered justification.

## Unchanged qualification and stopping rules

Every seed pair must satisfy integrity/finite-metric checks, N0 completion
>=99% (535/540), D0 >=95% (513/540), zero teleports, at least ten observed unique
D0 event-entry vehicles, an all-scheduled restricted-mean increase >=1 second,
queue increase >=5% with positive N0 denominator, and an eligible local-response
witness. No collisions, invalid routes, rerouting or prohibited new lane entries
are allowed. Exact mean/queue comparisons and status precedence remain in the
contract. These pilot thresholds are **not dissertation delta**.

Evaluate C1–C4 in order; the first level passing all three seeds requires an exact
first-seed N0/D0 repeat and durable readback. Do not continue to higher levels
after qualification, even if the repeat fails. The maximum future budget is
24 scientific runs plus two repeats, not current authorization. Technical or
integrity failures stop separately. If all levels definitively fail, retain
`NO_QUALIFYING_OD_CONCENTRATION`; do not tune the ladder or thresholds afterward.

## V2 correction and publication provenance

Accepted implementation candidate: `B0_OD_INPUT_AND_CUTOFF_MEASUREMENT_ADAPTER_V2`.
Protocol: `B0_OD_CONCENTRATION_CALIBRATION_CONTRACT_V1`. The differing version
numbers are intentional. The unchanged OD subcomponent retains
`B0_OD_INPUT_ADAPTER_V1`; cutoff observer identity remains
`B0_CUTOFF_EXPOSURE_OBSERVER_V1`.

V1 could accumulate two individually finite native waits of `1e308` into
infinity and still return `VALID` with no diagnostic. The preserved 540-trip C1
counterexample uses departures at scheduled time +1, arrivals at +101, those
two large waits, and otherwise zero waits/queue/halting. It tests numerical
validity, not physically plausible waiting or traffic performance.

V2 checks the waiting total after arithmetic. Overflow returns
`INTEGRITY_FAILURE` with `AGGREGATE_NATIVE_WAITING_NONFINITE` and a null waiting
total. Every scheduled row and contribution remains; there is no clamping,
partial sum, zero replacement or new physical threshold. A final floating-metric
check also makes any nonfinite metric unavailable with
`AGGREGATE_METRIC_NONFINITE:<metric_name>`. Other valid aggregate inputs are
bounded by the population/horizon; integer counts remain exact. Individual
validation and arithmetic order are unchanged. Native float addition overflows
to infinity without raising a numerical exception. Arbitrarily large integer
conversion can still raise before a result; universal structured handling of
every malformed input is not claimed.

| Public artifact | Projection from the verified freeze | SHA-256 of public bytes |
|---|---|---|
| [OD input source](../../scripts/b0/od_concentration_v2/od_input.py) | Byte-identical | `b78482335713b029eba50c62eb1f3a3a1976399ededf3bf749ab49e91a5db8a3` |
| [Measurement source](../../scripts/b0/od_concentration_v2/cutoff_measurement.py) | One path-expression change only | `88dcdeafd174392758d74cc62a3ca3932632692248b620d1955d9df0442938cb` |
| [Scientific Contract V1](../../configs/b0/od-concentration-v1/calibration-contract.json) | Byte-identical | `a450405a7e14ea7c099edb7bf9cd8598b72b3d392444c08c8ba481e96902284b` |

The measurement loader's expected observer path now resolves from its public
package to the existing [public observer](../../scripts/b0/exposure_observer.py).
The exact-path, non-symlink and SHA checks remain. The explicit hash-bound factory
is retained; no observer code was copied or modified. All remaining measurement
source bytes match frozen V2. Tests use normal public package imports.

The four original test files retain all 88 methods/assertions with import/path
relocation only. Thirteen correction tests retain their coverage. Four tests
formerly compared against V1 execution; their full synthetic output/ledger/metric
comparisons now use fixed canonical-JSON hashes recorded from verified frozen V2
outputs, whose representative valid cases matched V1 in the correction audit.
This is regression locking, not a new independent numerical oracle; the original
hand-computable tests remain. V1 is neither shipped as an active implementation
nor imported by public tests. Its unchanged historical report and separately
recorded expected failing assertion remain historical, not V2 release failures.

[Public fixtures](../../tests/b0_od_v2_fixtures.py) reconstruct the exact C1 input
and check its frozen XML hash. All twelve XML identities and logical assignment
digests are available for reconstruction; redundant generated XML files are not
published. Temporary-file readback tests verify the persisted format, including
the existing terminal newline. No raw simulation outputs, private freeze
manifests, machine receipts or historical exception tracebacks are included.

## Measurement and integration boundaries

Completed visits retain genuine exits/durations. Open visits become
`RIGHT_CENSORED_AT_CUTOFF` (the contract's `RIGHT_CENSORED_AT_H` semantics): true
exit/duration fields remain null and observed follow-up/lower bounds remain
separate. No exit, arrival or waiting-end event is fabricated. Censored visits
retain exposure and lane-entry/re-entry accounting. Missing steps are rejected,
not disguised as censoring. Local witnesses use eligible completed comparisons
or genuine valid arrivals; unavailable comparisons remain `NOT_IDENTIFIABLE`.

All scheduled trips appear once in reconciled terminal accounting and restricted
mean/P95 denominators. Active and independently proven undeparted trips retain
`H - scheduled_departure`. Missing tripinfo alone never proves nondeparture.
Undeparted native waiting is zero only under the frozen recognized null/missing/
zero rule; invalid departed waiting stays deficient, and no negative waiting
sentinel is invented. Native waiting, departure delay and custom queue/halting
remain distinct.

There is **no integrated qualification consumer, output writer or execution
orchestrator**. `completion_gate` evaluates supplied counts, and the local reader
evaluates supplied summaries/ledgers; neither validates an entire measurement
result. Future integration must reject non-`VALID` measurements before any
qualification decision, preserve null metrics, and never replace them with zero.
A numerical evidence failure must not become ordinary scenario nonqualification.

Future integration must serialize the entire candidate payload with strict JSON
(`allow_nan=False`) and validate before publishing a completed output file.
Valid and controlled-overflow payloads pass strict roundtrip tests. Preserved raw
numeric NaN/Infinity causes strict serialization to reject the payload, even
though usable metrics are already safe. No operational writer enforcement or
end-to-end status propagation is claimed.

## Offline validation and current gate

Verified publication base: `main` at `eccc2bb2a3318ac364396a828a4d0a0106d9e764`,
after fetching origin. CPython 3.12.14, standard library, synthetic inputs only:

| Test surface | Passed |
|---|---:|
| Original adapter cases: OD / cutoff / accounting / local response | 9 / 19 / 42 / 18 |
| Corrected aggregate and strict-output cases | 13 |
| Added public reconstruction/readback and binding cases | 2 |
| Unchanged public observer / calibration regressions | 15 / 35 |
| Total | 153 |

Zero failures, errors, skips or collection errors; 175 subtest callbacks, counted
separately. The difference from historical 151 is the two public-projection
tests, not deleted or weakened coverage. Eleven source/test files compiled in
memory. Completed/censoring compatibility, all twelve input readbacks, strict
JSON and exact public dependencies passed. Process/socket and real simulator
imports were blocked by the validation audit; no forbidden attempt occurred.
Every ignored-workspace open was denied during public tests; none was attempted.
The existing public calibration test uses its inert import shim, not real TraCI.

Reproduce the B0-only test surface from the repository root:

```sh
python3 -S -B -m unittest discover -s tests -p 'test_b0*.py'
```

No repository lint configuration is present; compilation and diff-whitespace
checks are the applicable static checks. The full repository suite was not run:
it includes out-of-scope Candidate N/provisioning and subprocess-probe surfaces.
This checkpoint validates the complete relevant B0 surface, not those systems.
Internal source/diff review is not independent external approval.

Live callback alignment, SUMO acceptance of generated XML, actual unfinished
output/sentinel handling, strict writer integration, and integrated qualification
remain unvalidated. Independent source review is pending. No simulator or
calibration is authorized by this publication.

```text
LIVE_INTEGRATION_VALIDATED=NO
OUTPUT_WRITER_IMPLEMENTED=NO
OD_CALIBRATION_EXECUTED=NO
SELECTED_CALIBRATED_OD_CONCENTRATION=NONE
DISSERTATION_DELTA_REMAINS_UNSET=YES
READY_TO_RUN=NO
```

Next gate, not executed: independently review the V2 public draft PR before
merge. Merging and any later live validation require separate authorization.
