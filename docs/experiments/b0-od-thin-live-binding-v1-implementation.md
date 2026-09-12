# Thin B0 OD binding V1 — native factory offline checkpoint

The latest state is the [native-factory completion below](#native-factory-completion--10-september-2026).
The preceding partial checkpoint is retained as historical provenance, including
its then-unresolved factory status, tests and identities. Those historical
statements do not describe the newly added native factories.

## Historical partial checkpoint

Work dates: 2026-09-09–10. Status:
`IMPLEMENTATION_PARTIAL_NATIVE_FACTORY_UNRESOLVED`.

The actual thin plan/collector and injected ownership path are implemented, but
there is **no native process or transport factory**. Passing a timeout argument
to an injected factory is a protocol obligation, not proof that native process
creation, connection acquisition or transport is bounded. This checkpoint must
not be represented as a completed live binding or as ready for a simulator run.

## Provenance and scope

Work continues on `feature/b0-od-live-binding-v1` at HEAD
`c0be5ca5c0116179f901bd00410c74e581799c87`. The existing uncommitted finalization
work is expected work, not something to reset from `main`. Before this
continuation, the fifteen source/test/document files in the reviewed export were
checked against its recorded identities. The
[schema-2 implementation checkpoint](b0-od-finalization-extension-v1-implementation.md),
[reviewed proposal/amendments](b0-od-finalization-contract-extension-v1-proposal.md),
[historical stop note](b0-od-live-binding-v1-stop-note.md) and original
characterization remain historical records rather than being relabelled.

**User-reported independent review:** no new blocker was found within the
exported finalization implementation's offline scope; the reviewer ran thirty
isolated validator/raw-writer tests. That was not a rerun of the historical
124 + 153 = 277 project tests, a native simulator check, formal approval or
execution authorization. Current continuation validation is recorded separately
below; no historical count is presented as a newly executed result.

## Implemented interfaces

| Module | Interface and responsibility |
| --- | --- |
| [`live_binding.py`](../../scripts/b0/od_integration_v1/live_binding.py) | `build_launch_plan(...) -> LaunchPlan` checks the accepted binding, exact materialized input files, explicit unprivileged port, executable/client file identities and protocol declaration; constructs deterministic argument order and rejects overrides. `validate_plan(plan)` reconstructs and compares the plan without launching anything. |
| Same module | `normalize_control_payload(binding, payload)` re-derives canonical controls from retained native options, input identities, loaded paths and TLS records. `PermissionLane` retains native getter pairs and projects their shared mask. `BindingConnection` exposes that projection without replacing the existing integration loop. |
| Same module | `NativeCollector(plan, runtime, connection, references)` anchors the actual original TripInfo object before close. `controls(view)`, `permissions()` and `diagnostics(view)` collect separate observed representations. `finalize_output(result) -> None` supplies process observations, original/retained bytes, diagnostics and run/binding capture incrementally. |
| Same module | `observe_owned(plan, *, bounds, process_factory, transport_factory, references) -> OwnedObservation` composes one injected owner, connection, collector and the existing `observe_run`. It contains no calibration ladder, automatic retry or default native launcher. Scientific run evidence and local ownership outcomes remain separate. |
| [`owned_runtime.py`](../../scripts/b0/od_integration_v1/owned_runtime.py) | `RuntimeBounds(startup, connect, transport, close, wait, terminate_wait, kill_wait)` requires finite positive bounds. `OwnedRuntime.start()` acquires at most one process/connection. `close()` attempts transport close, process wait, terminate/wait and kill/wait as needed, retaining first failure and later cleanup outcomes. A second close does not repeat acquisition or cleanup. |
| [`native_mapping.py`](../../scripts/b0/od_integration_v1/native_mapping.py) | `normalize_permissions(allowed, disallowed)`, `diagnostic_payload(raw, *, evidence_kind, finalized, stderr=None)` and `parse_diagnostics(payload, *, evidence_kind)` implement versioned, read-only representation checks. No SUMO/client import, process creation or socket operation occurs in this module. |

`process_factory(plan, timeout=...)` and
`transport_factory(process=..., plan=..., timeout=..., transport_timeout=...)`
are explicit injected dependencies. Their adapters must enforce deadlines in
actual I/O and clean up resources acquired but not returned. The owner cannot
clean an unknown process handle if acquisition raises before returning it. The
offline doubles exercise these interfaces; they do not establish that an
unimplemented native adapter obeys them.

## Native compatibility resolved statically

The intended installed framework metadata resolves to SUMO **1.27.1**; its
Python/C++ client constants declare TraCI protocol **22**. These are static
file/metadata observations, not the result of executing `sumo --version` or a
live `getVersion()` query. The future collector checks an observed runtime
version separately. Source inspection did not import the client or invoke a
binary.

### Permissions and controls

Native allowed/disallowed getters derive from one permission mask. An empty
allowed list alone is ambiguous: unrestricted and fully prohibited states need
the complementary disallowed view to distinguish them. The mapper checks both
views against the versioned canonical class universe before emitting the
disallow-based representation, retaining the raw pair. Deprecated aliases and
`ignoring` are not canonical returned classes; `rail_fast` is a distinct class
in the versioned native table. [Lane implementation](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/libsumo/Lane.cpp),
[class identities](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/utils/common/SUMOVehicleClass.cpp),
[canonical name lookup](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/utils/common/StringBijection.h).

Runtime option queries return effective string values. TLS programs return an
integer type (`0` for static), numeric phase durations and native phase objects,
not XML attribute strings. Static TLS `getParameter(..., "offset")` and
`"cycleTime"` provide seconds; the phase index is not an offset. The collector
retains these observations and normalizes finite numeric values explicitly.
Loaded network/route/output paths are checked against launch arguments; actual
file hashes and static contract/allocation labels are distinguished from runtime
queries. No expected-control dictionary alone can establish LIVE controls.
Queried and argument path/port observations are retained under the existing
`output_identity` operational container and revalidated on readback. This uses
the frozen operational exclusion rather than adding a repeat exception for
run-specific paths or ports; the nine scientific repeat families are unchanged.
[Simulation options](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/libsumo/Simulation.cpp),
[static TLS parameters](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/microsim/traffic_lights/MSSimpleTrafficLightLogic.cpp),
[native phase defaults](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/microsim/traffic_lights/MSPhaseDefinition.h).

### Populations, timestamps and waiting

Installed `simulation.getPendingVehicles()` describes vehicles delayed before
insertion, not arbitrary future scheduled demand. The binding uses that native
getter; it does not manufacture pending IDs from future departures. The frozen
pilot cutoff is after the complete scheduled departure window. Active IDs and
departure/arrival callbacks still flow through the accepted observation and
accounting logic.

Unfinished and undeparted output flags are distinct. The current plan requests
`tripinfo-output.write-unfinished=true` and
`tripinfo-output.write-undeparted=false`. Native undeparted output, if enabled,
covers delayed trips due by current time and implies unfinished output; it is
not an inventory of future demand. Native TripInfo preserves actual departure
or `-1`, unfinished arrival `-1`, and accumulated waiting values. No blanket
timestamp adjustment, XML rewriting or negative waiting sentinel is introduced.
Only the unchanged Adapter V2's existing full-cutoff proof may assign zero
waiting to a genuinely proven undeparted trip with absent native waiting.
[Output options](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/microsim/MSFrame.cpp),
[TripInfo output semantics](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/microsim/devices/MSDevice_Tripinfo.cpp).

### Diagnostics and finalization

`SUMO_1_27_1_ERROR_LOG_V1` retains both error-log and owned stderr bytes via
lossless base64. The error-log receives warnings as well as errors, and is
attached after some startup output may already have reached stderr. The mapper
therefore cannot certify full coverage from an empty error-log alone. The plan
requires English messages, warnings enabled, warning aggregation disabled,
verbose disabled and no timestamp/process-ID prefix. These are checked as
effective options, not inferred from requested arguments alone.
[Message routing](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/utils/common/MsgHandler.cpp),
[reporting options](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/utils/common/SystemFrame.cpp).

An explicit version-mapped collision warning or route finding and a native
`Error:` observation remain positive support. A warning is not automatically a
simulator error. Unknown messages, invalid UTF-8, missing streams and incomplete
acquisition retain any accessible positive findings but leave unsupported zeros
as `None` and coverage incomplete/unavailable. Counts are maximum supported
per-stream message occurrences, not unique collision or vehicle cardinalities;
their use is limited to the frozen zero-tolerance gates. They are not additional
traffic metrics. The actual collision-warning forms are tied to the versioned
[lane implementation](https://raw.githubusercontent.com/eclipse-sumo/sumo/v1_27_1/src/microsim/MSLane.cpp).

The collector records the intended TripInfo device/inode before finalization,
without inventing a content digest while output may grow. Original bytes are
read through bounded, no-follow, regular-file checks and retained separately.
Diagnostics are acquired before TripInfo so that a missing TripInfo cannot erase
an accessible diagnostic contradiction. Capture binds process/output observations
to the exact run, condition, binding and evidence origin. Integration remains the
owner of `collection_state` and parsing; process exit and completed acquisition
are not automatic scientific PASS. The existing shared validator and strict
writer/readback interpret retained evidence, not an unchecked severity sidecar.

### Installed client identities

The following SHA-256 values identify text files under the intended framework's
`share/sumo/tools/traci/` directory. They are dependency-source observations, not
machine receipts or proof of executed-binary compatibility.

| Client file | SHA-256 |
| --- | --- |
| `constants.py` | `42fa43f203bac2194b0758e8a7fba50873d3d4043648ab69cc58dc62a29e66dc` |
| `connection.py` | `05820ab615a2ab18411e9722ebbc7056856f2de155383a8b58120d2b2feac572` |
| `_simulation.py` | `8b7f97ced4dd6774271e8e0da270d687aa9a5ff438c8090023a941beb4e8bbec` |
| `_trafficlight.py` | `4757c6336d7edf37a7d1473d050731e40a18e4a4d9220babb564af2abaaac4c9` |
| `_lane.py` | `1b785163f695807cb8ea129cba9c42f243f3974a4a0d3d49ed442f362f043e6a` |
| `_vehicle.py` | `4c6bcdad2628f044ce235188f0269d6a5bcaf47e7836396d363280ecb91f0328` |

## Deltas to the reviewed schema-2 implementation

These changes extend the reviewed finalization implementation; they do not
reclassify its historical synthetic validation as live evidence.

- `integration.py`: explicit run/input origin support; narrowly added read-only
  native getters; normalization/readback of retained native control and permission
  representations; unavailable per-step native diagnostic observations instead
  of invented zeros. LIVE controls require native representation support. Current
  source binding includes the added modules. A native unchanged-clock abort with
  unavailable simulator-error coverage deliberately remains unsupported/FAIL;
  this change does not expand the accepted BLOCKED abort taxonomy.
- `finalization.py`: reference grants/capture bind evidence origin; native
  diagnostic mapping is dispatched alongside the original explicitly synthetic
  mapping. Native finalized-stream claims must agree with observed process state.
  The same validator retains first failure and composes later witnesses.
- `qualification.py`: reject mixed-origin pair/session/repeat histories and
  retain origin on replayable decisions. Synthetic selected-level labels remain
  synthetic; the LIVE label does not activate selection or authorize execution.
  Qualification, repeat comparison and stopping rules remain the existing ones.
- `evidence.py`: carry matching origin through input/payload, pending latch,
  completion marker, receipt and readback; reject origin mismatch. Schema-2
  records and schema-1 completion protocol remain distinct. No writer-limit or
  completion-protocol replacement is introduced.

Scientific Contract V1, Adapter V2, 540-trip allocations, seeds, metrics,
thresholds, nine repeat families, six operational exclusions, stopping rules,
24 + 2 simulation budget and 64 MiB evidence bound remain frozen. Schema-1
historical runs retain explicit read-only legacy auditing; they are not silently
upgraded into new schema-2 evidence. No second generator, accounting, selection
or persistence stack is introduced.

## Offline verification of this continuation

The final frozen-source runs used the installed isolated Python 3.12 runtime
with these existing commands (no simulator/client import or native execution):

```sh
python3 -I -S -B tests/run_b0_od_integration_offline.py new
python3 -I -S -B tests/run_b0_od_integration_offline.py existing
```

| Surface | Tests | Subtests | Harness seconds | Result |
| --- | --- | --- | --- | --- |
| Combined integration, including native binding/mapping/ownership tests | 210 | 355 | 450.228 | PASS |
| Existing B0/Adapter regressions | 153 | 175 | 1.878 | PASS |

Both report zero failures, errors, skips, collection errors and forbidden-access
attempts, with checked source/manifest hashes unchanged. The combined disjoint
total is 363 tests and 530 subtests. In-memory compilation of the twenty current
Python source/test files, whitespace checks and all eleven frozen dependency
hashes pass. The prior proposal, implementation report, stop note and historical
characterization bytes remain unchanged. The full 26-record synthetic selection
measures **56,936,193 bytes**, passing the unchanged 64 MiB bound and actual
write/readback/finalization. This is a synthetic serialization size, not a traffic
result or execution of the simulation budget.

Focused development checks are subsets of the combined integration surface and
are not added to its final total. The final focused subset passed 89 tests and
175 subtests before the full run. Earlier development included an interrupted
slow run (redundant reconstruction was reduced without changing observations)
and an interrupted integration run that found an unknown-mapping reason-code
compatibility regression. The established `UNSUPPORTED_DIAGNOSTIC_MAPPING` code
was restored without changing the existing test; the final complete run above
supersedes that unfinished run. Neither interrupted run is counted as acceptance.
Native-looking fixtures remain explicitly
synthetic. Their positive and late-contradiction paths use actual schema-2
assessment and persistence, but no native process/client is imported or started.

## Exact current identities and focused review delta

The [projection manifest](../../tests/reference/b0_od_integration_v1_projection.json)
records all twenty current source/test SHA-256 identities, the eleven accepted
dependencies, reviewed-export identities and earlier accepted checkpoints.
Its own SHA-256 is
`c582b3267a4472cce89d22f3ebe302afd4a69df79a7bf1e16eaeba845284917a`.
No source-hash substitution is runtime evidence.

Production paths below are under `scripts/b0/od_integration_v1/`.

| File | Current SHA-256 |
| --- | --- |
| `evidence.py` | `19146748f828369bc4286816f8725c560b8ede956677cc09e34cd1035bb501c2` |
| `finalization.py` | `990a2faf8ddd0029fd644e13101e1958eba50ed50c1486cd1b77d3ca6e5b2d86` |
| `integration.py` | `9c472cca52f50350fa5b4fa0bb851dd28d8a727f947bab288c97abea6e2ca82f` |
| `live_binding.py` | `5729d5c991e9c056145d7ae94e36e90a7b08775830f0b077d30c1622ba8f0303` |
| `native_mapping.py` | `04497999bf864c9e7f97f831bffe7ccad2f40403c807977bf6b34640a110a543` |
| `owned_runtime.py` | `d86f892316e0bdaf694ab054c7112d6e123c0001a8dab93467f88043f5be76b1` |
| `qualification.py` | `c7ba3158f9b222c0dd51337a8888b6f6462ed743abcc0e07b42daf880138f42c` |

The local ignored review artifact is
`.local-evidence/review-exports/b0-od-thin-binding-v1-2026-09-09/thin-binding-v1-focused.diff`.
It contains only this continuation's production/test/manifest delta against the
reviewed fifteen-file export, plus full added production/test files; it does not
mistake ordinary Git diff coverage for inclusion of untracked files. The export
archive identity is
`18da6341cc5d209bfc0d2d552e6f0b58853b372c974131e238d7f9876b3ec21b`.
This report, its short decision record and documentation navigation/progress
updates are separate from that focused code patch. No archive, private material
or entire ignored directory is copied into it.
The patch covers thirteen files (2,119 insertions and 63 deletions), includes all
seven new source/test files, and passes read-only reverse-application checking
against the current worktree. Its SHA-256 is
`04a2521c01b821e3b8bbb936bde8baa9385c527a75398ee727c8738f016205ba`.
Branch and HEAD remain unchanged; the index is empty. Expected prior and current
worktree changes remain unstaged/uncommitted, not reset or relabelled as clean.

## Single unresolved native interface and stop

**Bounded native acquisition of the process and connection remains unresolved.**
No factory implementing it was added. In particular, a requested process-start
timeout does not by itself bound native process creation before a process handle
is returned. [Python documents this process-creation timeout limitation](https://docs.python.org/3.12/library/subprocess.html#subprocess.run).
The installed Python client creates/connects a blocking socket,
receives synchronously and can wait on a process without a timeout. Its
post-connect hook cannot bound the preceding connect; `numRetries=0` limits
attempt count, not operation duration. The injected deadline/cleanup protocol
must not be described as native wall-clock enforcement.

Server listening scope is also unverified; a client destination of loopback is
not proof that the server listens only on loopback. No socket was opened to
inspect it. Live runtime identities, real output/callback behavior, ownership,
transport deadlines and actual listening scope remain future native validation
questions, not conclusions from synthetic success.

No success next-task recommendation is asserted at this partial checkpoint.
Resolving the native acquisition interface requires a separate bounded design/
implementation decision before any later review/publication or explicitly
authorized native check. No calibration, simulator, cloud, private Candidate,
RL, routing, commit, push, PR, merge, history rewrite or retained-ref change was
performed by this continuation.

```text
IMPLEMENTATION_STATUS=IMPLEMENTATION_PARTIAL_NATIVE_FACTORY_UNRESOLVED
NATIVE_PROCESS_FACTORY_IMPLEMENTED=NO
NATIVE_TRANSPORT_FACTORY_IMPLEMENTED=NO
LIVE_PROCESS_STARTED=NO
SIMULATOR_SOCKET_OPENED=NO
LIVE_INTEGRATION_VALIDATED=NO
OD_CALIBRATION_EXECUTED=NO
SELECTED_CALIBRATED_OD_CONCENTRATION=NONE
DISSERTATION_DELTA_REMAINS_UNSET=YES
COMMIT_CREATED=NO
PR_CREATED=NO
READY_TO_RUN=NO
```

## Native-factory completion — 10 September 2026

Status: concrete implementation present; final frozen-source offline validation
passed on the exact identities below. No native helper,
SUMO process, socket or installed-client import has been executed by this task.
The scientific apparatus is not ready to run or independently approved.

### Concrete entry points and ownership

| Entry point | Responsibility |
| --- | --- |
| [`native_supervisor.run_native`](../../scripts/b0/od_integration_v1/native_supervisor.py) | One later-authorized LIVE plan, explicit Python executable/SHA-256 and `SupervisorBounds`. Creates a single concrete isolated worker, runs the same production coordination tested with injected OS/IPC/clock operations, retains an operational receipt and independently checks any completed scientific handoff after cleanup. |
| `native_supervisor.supervise` / `NativeIPC` | Enforce the finite state/deadline boundary and actual nonblocking pipe operations. Only bounded control messages/receipts cross IPC, not a per-getter proxy or full traffic records. |
| [`native_worker.execute_worker`](../../scripts/b0/od_integration_v1/native_worker.py) | Run the existing plan, collector, schema-2 integration and strict writer/readback inside the worker. Default factories require LIVE origin, the established ownership gate and absolute supervisor deadlines. Injected offline factory pairs require SYNTHETIC origin. |
| `native_worker._spawn_native` / `_NativeProcess` | Concrete `Popen(plan.argv, ...)` plus actual finite child waits. SUMO inherits the already-owned worker process group; there is no detached child, shell, pre-exec hook or replacement launch. |
| [`native_transport.connect_native`](../../scripts/b0/od_integration_v1/native_transport.py) | Load the pinned installed client into the fresh worker and create the actual TCP connection. A worker-local socket facade applies remaining budgets to real connect/send/receive operations; it does not alter the installed package or the research process's global socket module. |
| `native_worker.validate_worker_result` | Re-read the strict result with one explicit worker-supplied, run/origin/directory-bound reference grant. Do not infer a new grant from stored run contents. |

Sequence: isolated worker bootstrap → independently verified PID=PGID=SID →
READY/GO → at most one SUMO acquisition → connect/handshake → existing observation
and finalization → strict worker persistence → scoped supervisor cleanup →
independent handoff readback. `DONE` is an IPC envelope, not part of the strict
scientific handoff payload or a declaration that the experiment passed.

### Absolute deadlines and expiry

All durations are explicit positive finite operational settings. Existing
`RuntimeBounds` remains unchanged; `SupervisorBounds` adds bootstrap, total,
finalize and cleanup durations without selecting execution values here.

| Boundary | Starts / enforcement / expiry |
| --- | --- |
| Worker bootstrap | Absolute deadline begins before the initial `Popen`. The call itself cannot be interrupted reliably by this supervisor; a returned late handle is cleaned and receives no GO. READY and setup must finish within the original remaining budget. |
| SUMO startup | Starts before GO is written, after independently verified worker ownership. Worker rechecks the supplied absolute deadline immediately before SUMO `Popen`. Parent IPC polling independently expires the phase even if acquisition never returns a child handle. |
| Connection/handshake | One absolute budget starts before native loading/connect/getVersion. The parent caps that single phase against total time. Only pre-handshake connection refusal can retry socket acquisition under the same deadline; no retry follows a successful TCP connection and SUMO is never relaunched. |
| Exchange | One paired BEGIN/END deadline encloses the complete framed socket exchange, partial sends, length-prefixed receives and parsing inside the wrapped Connection method. Every raw socket operation receives the remaining time; progress cannot renew the deadline. Remaining domain-getter value decoding is bounded by total execution, not this per-exchange interval. getVersion/simulationStep/close have their own wider wrapped methods. The parent independently rejects stalled or late exchange completion. |
| Total execution | Starts before GO and never resets at phase transitions. Covers acquisition, observation, finalization and worker persistence/handoff. |
| Close/finalization | Entered once before orderly close/wait. Parent caps it against total time. Native close uses a complete close-exchange deadline and `wait=False`; the existing owner performs separately bounded child waits. Failed IPC reporting cannot skip acquired-resource cleanup. |
| Supervisor cleanup | One new absolute cleanup budget covers TERM, finite grace, KILL and finite worker reap. Grace reserves budget for later operations. Cleanup is not a sequence of renewable full-duration waits. |

Duplicate/backward phase messages, unmatched exchange messages, late handles,
late results and cancellation cannot restore success or trigger a second launch.
Parent control/status pipes are nonblocking, message-size bounded and checked
against the same absolute deadline after partial I/O. The worker may block in
native/IPC/filesystem work; the independent parent remains the enforcement
boundary after bootstrap.

The worker applies the existing 64 MiB bound as `RLIMIT_FSIZE` before READY,
inherited by SUMO, to bound each generated file including stdout/stderr. This is
an operational per-file output bound, not a new scientific stopping rule. No
input allocation, metric, threshold, simulation timing or 24+2 budget changed.

### Cleanup proof, interruption and limitations

The supervisor retains the worker unreaped until its **last** exact-group
signal. It does not call `Popen.poll`, `send_signal`, `terminate`, `kill`,
`communicate` or a process context-manager exit while reserving the worker PID.
After scope verification, only the saved worker PGID is signalled; IPC child PIDs
are observations, never signalling authority. If verification fails before GO,
only the owned worker PID may be signalled. Post-handle pipe/setup exceptions
return that handle to cleanup and preserve earlier exceptions.

This relies on default SIGCHLD handling and exclusive ownership of child
reaping: a competing `waitpid(-1)` caller invalidates the PID-reservation
assumption. The entry rejects a non-default SIGCHLD handler, but cannot prove
the absence of another reaping thread. The future native gate must check the
caller environment. [Python process semantics](https://docs.python.org/3.12/library/subprocess.html#subprocess.Popen),
[Apple session semantics](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/setsid.2.html),
[child wait semantics](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/wait.2.html).

Successful TERM/KILL delivery or worker reaping alone does not prove that SUMO
or its descendants are absent. A normal handoff can retain actual child-wait
evidence plus worker reaping; forced termination without that evidence retains
`child_scope=UNRESOLVED`. Cleanup errors and overruns are explicit, not invented
`PROCESS_STOPPED` or clean-finalization results. There is no process-name scan,
unrelated PID discovery, broad cleanup, daemon, pool or nested supervisor.

The initial OS worker bootstrap remains **not deadline-interruptible**. No SUMO
acquisition is permitted before the returned worker/session is verified, so the
previous SUMO pre-handle ownership gap is addressed; a stronger requirement to
interrupt that initial bootstrap is **not** satisfied. This implementation also
does not claim hard real-time behavior under arbitrary kernel/filesystem failure
or cleanup after the supervisor is forcibly killed outside its cancellation
handler. Post-cleanup receipt/readback is bounded-size ordinary filesystem I/O,
not an independent hard real-time filesystem guarantee.

The worker preserves the integration's chronological first failure and supported
later contradictions. The supervisor retains its first observed failure,
worker failure payloads, late messages and later cleanup findings. Forced death
can make additional worker observations unavailable; it cannot justify inventing
them. An interruption receipt is separate from schema-2 scientific evidence.
Already-written output remains available, but unfinished finalization is not
relabelled complete or qualified. Native exception classes are preserved: a lost
connection does not prove an unchanged clock or become blanket BLOCKED.

### Current source changes, validation and review export

This completion adds three production modules and four test modules. No prior
production module was refactored or modified. The projection test/manifest now
bind the added files and retain the prior twenty-file checkpoint identities.
The earlier reviewed finalization proposal/report, characterization and eleven
frozen dependencies remain byte-identical. The manifest lists all current
production/test hashes; exact completion-source identities are:

| New production module | SHA-256 |
| --- | --- |
| `native_supervisor.py` | `9bf22935df3078ba51384625541dc19bd57306f811346e895efefb6ba8d4c1ad` |
| `native_worker.py` | `6202db3d60752a1c737e4ec01abeae42707846e91bbd7d22bbc2efca8e1701b4` |
| `native_transport.py` | `50c9b4bcd3a6794604bfd94fa221a403e1ff1ebd3ffa4790eb9863d9ac8c5cf2` |

Final frozen-source commands use Python 3.12 with `-I -S -B`:

| Command | Tests | Subtests | Harness seconds |
| --- | ---: | ---: | ---: |
| `tests/run_b0_od_integration_offline.py new` | 310 passed | 467 | 474.777 |
| `tests/run_b0_od_integration_offline.py existing` | 153 passed | 175 | 1.818 |

Both report zero failures, errors, skips, collection errors and forbidden-access
attempts, with source hashes unchanged. These are 463 distinct tests and 642
subtests across the two complete surfaces, not additional experiment runs.
The full synthetic C4 payload is 56,943,083 bytes and passes actual strict
write/readback/finalization under the unchanged 64 MiB writer limit.
In-memory compilation, whitespace, document-link existence, exact projection
identities and all eleven frozen dependency hashes pass. All prior production
files remain unchanged by this completion. Branch and HEAD remain unchanged;
the index is empty and the expected uncommitted work is retained.

The current projection manifest binds twenty-seven production/test identities;
its SHA-256 is
`75e530eae0267328abdd937d04e1f151cf1a68e008b6db3220a0065b3154445b`.
Focused subsets are not additional counts. During development the DONE envelope
regression was reproduced and corrected; descriptor and reporting failure
cleanup regressions were also added. Offline tests inspect production
coordination, native-call arguments and remaining budgets through doubles,
including actual collector/assessment/writer positive and late-FAIL paths.

The updated review ZIP is prepared at
`.local-evidence/review-exports/b0-od-native-factory-v1-2026-09-10/b0-od-native-factory-v1-review.zip`.
It contains complete current changed/new public source, tests and small fixtures,
this note, the prior proposal/report and stop note, decision record, manifest,
focused accepted-base diff, validation summary and per-file inventory. Relevant
untracked files are included in full. Unchanged dependencies are referenced by
repository-relative path and recorded identity; Git internals, private mappings/
policy, credentials, correspondence and generated run evidence are excluded.
This combined snapshot is against accepted base
`c0be5ca5c0116179f901bd00410c74e581799c87`, including the preserved finalization
extension and prior thin-binding work, not just this completion's additions.
Documentation navigation and the longitudinal progress log remain outside the
focused export; the inventory identifies that deliberate scope.

Remaining later-native checks: actual isolated helper/client loading and exact
runtime version; real process-group inheritance, cancellation and reaping;
socket timing and complete-message deadlines; native callback/population/output
semantics and diagnostic coverage; actual server listening scope. A loopback
client destination still does not establish loopback-only server binding. The
six client files remain exact-hash pinned; installed helper imports are bound to
the selected sibling package location, not claimed fully hash-pinned.

No next task is executed by this completion. Review/publication and any bounded
native validation remain separate authorization gates.

```text
NATIVE_FACTORY_IMPLEMENTED=YES
DEADLINE_ENFORCEMENT_OFFLINE_VALIDATED=YES
PRE_HANDLE_OWNERSHIP_ADDRESSED=YES
LATE_ACQUISITION_HANDLING_VALIDATED=YES
CLEANUP_SCOPE_AND_LIMITS_DOCUMENTED=YES
BOOTSTRAP_LIMITATION_EXPLICIT=YES
EXISTING_REGRESSIONS_PASS=YES
NATIVE_PROCESS_TEST_EXECUTED=NO
LIVE_PROCESS_STARTED=NO
LIVE_INTEGRATION_VALIDATED=NO
OD_CALIBRATION_EXECUTED=NO
SELECTED_CALIBRATED_OD_CONCENTRATION=NONE
DISSERTATION_DELTA_REMAINS_UNSET=YES
COMMIT_CREATED=NO
PR_CREATED=NO
READY_TO_RUN=NO
NEXT_TASK=INDEPENDENTLY_REVIEW_COMPLETED_THIN_BINDING_BEFORE_PUBLICATION
```
