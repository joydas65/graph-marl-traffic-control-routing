# EXP-B0-CAL-001: Baseline-only uniform-demand calibration

## Status

Executed on 4 September 2026 and published on 5 September 2026.

- `CALIBRATION_STATUS=NO_QUALIFYING_DEMAND_LEVEL`
- `SELECTED_CALIBRATED_DEMAND_LEVEL=NONE`
- `DISSERTATION_EFFECT_THRESHOLD_REMAINS_UNSET=YES`

This is a valid negative calibration result, not a technical failure. The
validated B0 substrate and its separate 1X `TOO_WEAK` verdict remain recorded
in [`EXP-B0-000`](EXP-B0-000.md).

## Question and pretreatment boundary

The frozen question was: what is the lowest predeclared uniform departure-
density multiplier at which the A1B1 one-lane-loss event produces a
reproducible, non-catastrophic, directly exposed, scientifically measurable
fixed-time baseline response on all three calibration seeds?

The calibration preceded every RL, DQN, GNN, graph-communication, routing, and
dissertation treatment implementation. Future treatment results could not
influence selection. The designated calibration-seen corridor was `A1B1` /
`B1A1`; it is not eligible as a future headline held-out location. Seeds
`20260904`, `20260905`, and `20260906` are calibration seeds and are excluded
from the final confirmatory treatment estimate unless a later protocol
preregisters a justification for reuse.

## Frozen design

The ladder was `2X`, `3X`, `4X`, then `5X`, representing 360, 540, 720, and 900
scheduled trips. Each level retained the 12 B0 row/column routes, the fixed
network, 68-second TLS programs, 1,500-second horizon, no rerouting, and the
passenger restriction on `A1B1_0` during `[300,600)`.

The demand algorithm initializes `random.Random(seed)`. In each of fifteen
60-second blocks it shuffles `list(ROUTES) * multiplier` once and assigns slot
`k` to integer second `block * 60 + floor(k * 60 / (12 * multiplier))`. It uses
no other generator RNG calls. This gives equal per-route counts, preserves the
original route definitions, reproduces the frozen 1X route hash at multiplier
one, and uses the calibration seed only for route-to-departure-slot assignment;
the simulator seed remains `20260904`.

## Qualification contract

A seed pair qualified only if every integrity rule passed and all of these
inclusive scientific gates held:

- N0 and D0 completion were at least 0.99 and 0.95 respectively, with zero
  teleports;
- at least 10 unique D0 passenger entries to `A1B1` occurred during the event;
- D0 restricted mean trip time exceeded N0 by at least 1 second;
- D0 queue burden exceeded N0 by at least 5%; and
- at least one directly exposed vehicle showed additional `A1B1` traversal
  time, `A1B1` halting, or final-arrival delay.

A level qualified only if all three seed pairs qualified. Selection stopped at
the first qualifying level. The mean and queue gates used exact total/integer
comparisons rather than rounded display values.

The +1-second and +5% gates were pilot scenario-sensitivity heuristics only;
neither was the dissertation effect threshold δ. Dissertation δ was not
estimated or frozen by this calibration.

## Complete aggregate results

Each row is one matched N0/D0 pair; together the table covers all 24 measured
simulations. Queue burden is in vehicle-seconds and completion is shown as
N0/D0.

| Level | Seed | Trips | D0 exposure | N0 mean (s) | D0 mean (s) | D0−N0 mean (s) | N0 queue | D0 queue | Relative queue change | Completion | Qualification |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2X | 20260904 | 360 | 11 | 99.511111 | 99.619444 | +0.108333 | 14,672 | 14,702 | +0.204471% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 2X | 20260905 | 360 | 10 | 97.558333 | 97.561111 | +0.002778 | 14,063 | 14,056 | −0.049776% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 2X | 20260906 | 360 | 9 | 97.144444 | 97.158333 | +0.013889 | 13,935 | 13,936 | +0.007176% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 3X | 20260904 | 540 | 15 | 98.727778 | 98.737037 | +0.009259 | 21,709 | 21,694 | −0.069096% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 3X | 20260905 | 540 | 16 | 98.753704 | 98.692593 | −0.061111 | 21,690 | 21,654 | −0.165975% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 3X | 20260906 | 540 | 17 | 98.062963 | 98.068519 | +0.005556 | 21,338 | 21,324 | −0.065611% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 4X | 20260904 | 720 | 22 | 99.336111 | 99.337500 | +0.001389 | 29,218 | 29,191 | −0.092409% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 4X | 20260905 | 720 | 22 | 99.451389 | 99.454167 | +0.002778 | 29,272 | 29,244 | −0.095655% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 4X | 20260906 | 720 | 21 | 100.644444 | 100.648611 | +0.004167 | 30,025 | 30,014 | −0.036636% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 5X | 20260904 | 900 | 25 | 99.993333 | 99.953333 | −0.040000 | 36,820 | 36,750 | −0.190114% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 5X | 20260905 | 900 | 27 | 100.170000 | 100.174444 | +0.004444 | 36,919 | 36,887 | −0.086676% | 1.000/1.000 | `DOES_NOT_QUALIFY` |
| 5X | 20260906 | 900 | 28 | 100.194444 | 100.201111 | +0.006667 | 36,943 | 36,912 | −0.083913% | 1.000/1.000 | `DOES_NOT_QUALIFY` |

All integrity checks passed and every trip completed. Every pair definitively
failed both network-response gates. The 2X/`20260906` pair additionally missed
the exposure gate with nine event entries. No rounding was used to determine
these outcomes.

The descriptive across-seed summaries below are calibration observations only;
no inferential or central-hypothesis significance test was performed.

| Level | D0 exposure min/mean/max | Mean D0−N0 trip time (s) | Mean relative queue change |
|---|---:|---:|---:|
| 2X | 9 / 10.000 / 11 | +0.041667 | +0.053957% |
| 3X | 15 / 16.000 / 17 | −0.015432 | −0.100227% |
| 4X | 21 / 21.667 / 22 | +0.002778 | −0.074900% |
| 5X | 25 / 26.667 / 28 | −0.009630 | −0.120234% |

Only 3X/`20260906` produced the predeclared descriptive recovery signal: the
maximum positive excess queue was one vehicle at 618 seconds and was at or
below one vehicle by 619 seconds. This diagnostic is not a qualification gate
and is not a final dissertation recovery definition.

## Execution history

Attempt 1 stopped before SUMO observations because its local TraCI connection
did not receive a usable port. It produced no scientific measurement and does
not invalidate the completed calibration. Attempt 2 reused the unchanged
scientific sources and inputs, verified the sealed attempt-1 state, and ran in
an execution environment where the localhost TraCI socket was available. It
completed the 24 measurements above.

Because no level qualified, the protocol correctly performed no deterministic
repeat and froze no calibrated scenario.

## Demand identities

| Level | Seed | Generated route-file SHA-256 |
|---|---:|---|
| 2X | 20260904 | `17c17735fddd62f5ce385af60e310aa2978af66037b03755ebc7be4881b488ea` |
| 2X | 20260905 | `f249712fb7dac317d9c85e8860558d61379202107cb82b430fb80d9548847cc0` |
| 2X | 20260906 | `882b9def1b3cd84b41d68b7f730dab1bd9c927c34180726d5d9e9f7abb98e02c` |
| 3X | 20260904 | `e9738459d9555fe28e27bd07c6112d841d231aa2154a84cbc2d9cf732a08eeef` |
| 3X | 20260905 | `17c1bda124748945d09d86e45c4040e9672a1f0342c7b77cc8f29b714b624835` |
| 3X | 20260906 | `69638e864ac719b8821bb7e83fa1583b4e9d4fa81c04a461ef8e5306a41e99d6` |
| 4X | 20260904 | `a9311cdbcfbe69ab89d9b798bec4c42e0fc40520d900ed835acba4a9bef7247f` |
| 4X | 20260905 | `f32de8a3f79374990381ca38452132e40dc35381a797cba050cd54f45ad28f25` |
| 4X | 20260906 | `cdf340ca447621fc1599b58b0c43088c81bd0a6f7d988b5a601e39fcd635fa04` |
| 5X | 20260904 | `96af21c8c85451c72055a7703781bf23db32e817918f286c29e583e59331943d` |
| 5X | 20260905 | `f92dcc22b00daa613d655c78c128f558b68f19e35be1f7dd2d1b4d3c7a18f0a2` |
| 5X | 20260906 | `ec0ef7224fe40f5568712b15cfbd6bb6ac40d819e1a838db1efef1d199903803` |

## Provenance identities

| Artifact | SHA-256 |
|---|---|
| Frozen calibration contract | `3e3cbc4f822b7bb75974e21064b62d54a076dd1db7c38119aad81ea7ba6f3382` |
| Executed calibration runner | `f44035eac421d428877c356ecfef8c5aa9e0388a820c4b1421997c6346c9c3b4` |
| Executed attempt-002 resume driver | `5eb23bcaff130249f8dbb142d5b9d927fc28a1b8bf9caca7e50c75b6eaf71446` |
| Executed 35-test source | `1623488c515cdaaf21f9bb6388886437bbc604147421d6e81b67a9406208af63` |
| Frozen B0 runner | `d4286193089a8062ae16e51e3dbaf8f26df6be11d43399d6fd998941b275ccab` |
| Derived population-parameterized B0 source | `3023257bad6cbb0b651968192df96c41a4232d3e16a4bda927f2b48458d32a59` |
| Frozen observer | `dd582ab3011d3077c1ad1f63b95f26708813bf0628dcdee4bebda4c054a68d57` |
| Frozen network | `49b2c7a89a72083b0f894c6b7083558f0120059122237d960a907bafbcf62dd2` |
| Frozen disruption specification | `77df3a6504045f12815b6fe75ca7b00d370d568d1b5203d863f83385d536fb91` |
| Complete local calibration artifact manifest (not published) | `efa97a52b2ee516dfa671132bf803a5e792abd15e6ad80070ab51fcc983adbd1` |

The exact provenance sources and active offline tests are documented in the
[`scripts/b0/calibration` package](../../scripts/b0/calibration/README.md). Raw
simulator artifacts and environment receipts remain outside Git.

## Interpretation and decision

Across this frozen 2X–5X ladder, globally balanced traffic density did not meet
the predeclared network-response gates for the one-lane-loss event. Therefore
the first-qualifying selection is `NONE`, the dissertation effect threshold
remains unset, and this calibration does not test the central dissertation
hypothesis.

The single next baseline-only calibration axis is OD/corridor concentration at
fixed 3X total demand. Here 3X is only the fixed demand budget for that new
axis; it is not a selected calibrated demand level. That next experiment was
not performed in this publication task.
