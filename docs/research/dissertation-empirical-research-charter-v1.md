# Dissertation Empirical Research Charter v1

## Status and purpose

- **Status:** frozen pre-empirical research design
- **Version:** 1
- **Freeze date:** 4 September 2026
- **Empirical state at freeze:** no capacity-conditioned treatment result had been observed or produced

> This charter was frozen before observing treatment results. Revisions must be
> versioned and justified; confirmatory claims must not be retrospectively
> redesigned around observed treatment performance.

This document defines the smallest confirmatory empirical programme currently
capable of testing the dissertation's central claim. It supersedes broader
working scope as the authority for the initial treatment experiment, while
preserving earlier roadmap documents as historical planning records.

## Provisional primary research question

> Under temporary localized road-capacity reductions, does conditioning
> inter-agent graph communication on current link capacity and availability
> reduce fixed-horizon door-to-door trip-time burden at disruption locations
> withheld from training, relative to an otherwise matched static-graph signal
> controller receiving the same local disruption observations?

The question is intentionally narrower than generic dynamic-graph, graph-MARL,
resilient-control, or joint-routing questions.

## Central falsifiable hypothesis

> On preregistered held-out-location episodes with temporary single-link partial
> capacity reductions and fixed vehicle routes, a capacity/availability-conditioned
> graph signal controller will lower demand-normalized restricted mean door-to-door
> trip time by at least a preregistered smallest meaningful effect δ relative to an
> architecture-, observation-, reward-, action-, and training-budget-matched
> static-graph controller, without materially reducing throughput or increasing
> unfinished trips; it is falsified when a sufficiently precise paired confirmatory
> analysis supports an effect below δ or harm, or either guardrail breaches its
> frozen tolerance, while inadequate precision is `INCONCLUSIVE`.

The numerical value of δ and the throughput and unfinished-trip guardrail
tolerances are deliberately **not set in v1**. They will be justified using
traffic relevance and baseline-only pilot variability, then frozen before any
confirmatory treatment evaluation. Treatment results must not be used to choose
or revise them.

For sign consistency, define the primary treatment effect as
`Δ_primary = Y_B3 - Y_T0`, where `Y` is the burden outcome defined below.
Positive values favor T0, and the central hypothesis requires
`Δ_primary ≥ δ` together with both guardrails.

## Secondary hypotheses

1. **Propagation and recovery.** Relative to disruption-informed independent
   control A0/B1, capacity-conditioned graph control A3/T0 will reduce excess
   queue propagation by graph distance and shorten recovery following the
   capacity reduction. The conjunctive hypothesis is falsified if either
   preregistered directional effect is absent or reversed with sufficient
   precision.
2. **Held-out severity.** Any benefit of capacity-conditioned communication will
   persist at preregistered capacity-reduction severities absent from training.
   The hypothesis is falsified if the benefit is absent, reversed, or confined
   to trained severities.
3. **Conditional routing extension.** If the routing gate is opened, frozen
   coordinated routing T1 will add meaningful value beyond otherwise matched
   uncoupled routing R0 without worsening unfinished trips, tail delay, training
   stability, or origin-destination burden. A separate R0-versus-T0 contrast
   will test the value of adding routing at all. Failure of the T1-versus-R0
   coordination contrast removes coordinated routing from the dissertation
   core.

These are secondary claims. They cannot replace or rescue an unsupported
primary hypothesis.

## Minimum novelty boundary

### Baseline functionality

Deterministic SUMO operation, legal phase transitions, demand and disruption
generation, fixed-time and independent-RL baselines, seed control, metrics, and
raw evidence preservation are essential research infrastructure. They are not
the dissertation-specific treatment.

### Inherited or public graph mechanism

A verified fixed-topology graph controller that communicates traffic state
between intersections is the graph baseline. Graph neural networks, MARL,
attention, and static or learned traffic-dependent edge weights are not novel
by themselves.

### Dissertation-specific treatment

The minimum treatment is a graph signal controller in which current physical
residual capacity or availability directly changes message admission or graph
weighting under a frozen disruption split. The required causal path is:

> physical link condition → communication mask/weight → received neighbor
> representation → signal action

Merely adding capacity or availability to an observation does **not** establish
this mechanism. The architecture beyond this causal boundary remains open and
must not be expanded for novelty's sake.

## Baseline hierarchy

| ID | Controller | Scientific alternative ruled out |
|---|---|---|
| **B0** | Deterministic fixed-time signals with fixed routes | Provides a non-adaptive reference and validates the simulator/metric pipeline; it can indicate whether adaptation may help but cannot establish that learning, rather than another adaptive controller, is necessary. |
| **B1** | Independent RL with matched local disruption observations and fixed routes | Tests whether local adaptation and disruption sensing alone explain the result. |
| **B2** | Static-graph RL without explicit disruption information and with fixed routes | Establishes ordinary graph-coordination behavior under disruption without privileged capacity information. |
| **B3** | Static-graph RL with the same local disruption observations as T0 and fixed routes | Primary comparator; holds all non-treatment architectural components and parameterization, sensing, input, reward, action, and training budget fixed so that the intended communication-operator change is isolated. |
| **T0** | Capacity-conditioned graph signal controller with fixed routes | Core treatment; isolates the signal-side effect of capacity/availability-conditioned communication. |

B0 through B3 and T0 are the minimum core. If the routing gate is later opened,
`R0` will denote frozen T0 signals plus uncoupled slow routing, and `T1` will
denote explicitly coordinated signal and routing decisions. Neither is part of
the initial confirmatory question.

## Core ablation matrix

Routes, actions, reward, training budget, scenario seeds, and all
non-disruption observations remain fixed across the relevant learned methods.

| ID | Graph communication | Explicit local disruption information | Capacity-conditioned communication | Interpretation |
|---|---:|---:|---:|---|
| **A0** | Off | On | Off | Independent disruption-informed RL |
| **A1** | Static | Off | Off | Ordinary static-graph coordination |
| **A2** | Static | On | Off | Disruption-informed static graph; the primary matched comparator |
| **A3** | Conditioned | On | On | Capacity-conditioned treatment |

For every burden or loss outcome below, define a contrast as comparator minus
the more informed treatment, so a positive value favors the latter. The planned
explanatory contrasts are:

- **`Y_A2 - Y_A3`:** effect of capacity-conditioned communication;
- **`Y_A1 - Y_A2`:** effect of supplying explicit disruption information;
- **`Y_A0 - Y_A2`:** effect of graph coordination under equal local observability;
- **`Y_A0 - Y_A3`:** total treatment effect, which is not sufficient by itself to
  identify the mechanism.

Routing and fast/slow timescale changes are excluded from this core matrix.

## First disruption family

`FIRST_DISRUPTION_FAMILY=TEMPORARY_SINGLE_LINK_PARTIAL_CAPACITY_REDUCTION`

This family permits controlled onset, duration, severity, and physical
location; preserves route feasibility; and creates interpretable spillback and
recovery behavior. It directly matches the proposed communication mechanism.

The provisional taxonomy is:

1. temporary partial link-capacity reduction or lane loss — first family;
2. demand surge — later secondary stress family;
3. full closure or severe incident — deferred until reachability and routing
   confounds can be controlled.

Exact severity values, durations, onset times, and physical locations are not
set in this charter.

## Train, validation, and test split

- Partition eligible physical disruption zones before model training. Opposite
  directions, adjacent approaches, or other representations of one physical
  incident zone must remain in the same partition to prevent spatial leakage.
- Training may use normal episodes and mild/moderate partial reductions only at
  declared training locations.
- Validation uses separate scenario seeds and validation locations for model
  selection and protocol checks. Test locations must never influence tuning.
- The primary test uses untouched physical disruption locations after the
  controller, metrics, seeds, exclusion rules, δ, and guardrails are frozen.
- A preregistered held-out severity is secondary. A location-by-severity stress
  test is also secondary. An unseen network remains a stretch claim.

No test-location episode may be reclassified as training or validation after
its result is observed.

## Outcomes and guardrails

`PRIMARY_OUTCOME_METRIC=DEMAND_NORMALIZED_RESTRICTED_MEAN_DOOR_TO_DOOR_TRIP_TIME_OVER_A_PREREGISTERED_HORIZON_PLUS_CLEARANCE_WINDOW`

For a frozen demand set of `N` scheduled trips, scheduled departure `s_i`, valid
arrival `a_i`, and final cutoff `H`, the primary outcome is

`Y = (1/N) Σ_i [min(a_i, H) - s_i]`.

For a trip without a valid completed arrival by `H`, `a_i` is treated as beyond
the cutoff. It therefore contributes accrued burden through `H`; it is never
dropped or counted as a success. The outcome is restricted to the predeclared
horizon plus clearance window and does not impute unobserved post-cutoff travel.

### Secondary outcomes

- demand-normalized cumulative queue burden in vehicle-seconds;
- demand-normalized cumulative waiting burden;
- restricted trip-time tail, provisionally the 95th percentile; and
- spatial and temporal recovery diagnostics defined below.

Reward is a learning signal, not an empirical outcome.

### Guardrails

- non-teleported throughput by the cutoff; and
- unfinished-trip count and fraction.

Unfinished demand must be partitioned into not departed, active in the network,
teleported, and otherwise failed. A claimed primary improvement is invalid if a
frozen throughput or unfinished-trip guardrail is breached. The numerical
tolerances will be determined from traffic relevance and baseline-only pilot
variability before treatment evaluation; they are not set here.

## Generalization claim boundary

| Generalization target | Status |
|---|---|
| Unseen physical disruption location | `PRIMARY` |
| Unseen disruption severity | `SECONDARY` |
| Unseen demand | `SECONDARY` |
| Unseen network | `STRETCH` |

Success on one category must not be described as evidence for another. In
particular, unseen demand or a new network is not equivalent to a held-out
physical disruption location.

## Statistical principles

- Use multiple independent training seeds for stochastic methods.
- Treat training runs and independent scenario blocks as replication levels;
  vehicles and timesteps are not independent experimental replicates.
- Apply the same frozen demand and disruption scenario blocks to comparable
  methods and use paired analysis where that pairing is valid.
- A shared numeric initialization seed does not by itself pair models with
  different architectures.
- Freeze confirmatory seeds before treatment evaluation and never select seeds
  after observing favorable outcomes.
- Report absolute effects in seconds per demanded trip, relative effects,
  central tendency, uncertainty intervals, tail behavior, and run success rate.
- Respect nesting through an appropriate hierarchical or seed/block resampling
  analysis.
- Keep one primary outcome and one primary contrast. Treat secondary analyses
  with declared multiplicity handling or label them exploratory.
- Retain and classify failed runs, teleports, and unfinished trips. Do not
  silently exclude them.
- A wide uncertainty interval is `INCONCLUSIVE`, not evidence of equivalence.

Baseline-only pilots may determine computational budget, runtime, traffic
volume, variance, skew, failure rate, desired precision, final seed count, δ,
an equivalence margin, and guardrail tolerances. These choices require traffic
meaning as well as statistical variability. Treatment pilots must not tune
confirmatory thresholds; if run, they remain explicitly exploratory and outside
the confirmatory dataset.

## Mechanism diagnostics

At most these five diagnostics support the core mechanism claim:

1. excess queue burden over time, stratified by graph-hop distance from the
   disrupted link;
2. right-censored recovery to a baseline-only predictive envelope for a
   preregistered sustained window;
3. time-lagged upstream/downstream discharge-flow alignment around the event;
4. spatial dispersion and tail burden across junctions or origin-destination
   groups, exposing burden displacement; and
5. frozen-policy neighbor-message mask or shuffle sensitivity without
   retraining.

The predictive envelope and sustained recovery window are intentionally
unresolved until baseline-only behavior is characterized.

## Failure and simplification criteria

- **Reject the central hypothesis** if a sufficiently precise confirmatory
  analysis supports harm or an effect below the frozen δ, or if a frozen
  throughput/unfinished-trip guardrail is breached. Insufficient precision is
  `INCONCLUSIVE`.
- **Simplify the method** if removing capacity conditioning or explicit
  disruption information is non-inferior within the frozen margin while
  improving stability, runtime, or interpretability.
- **Abandon graph coordination as the claimed contribution** if a capacity- and
  budget-matched independent controller is non-inferior and graph/message
  diagnostics reveal no credible coordination mechanism.
- **Remove routing from the dissertation core** if its later matched incremental
  test has no meaningful benefit or worsens unfinished trips, tail delay,
  origin-destination burden, reliability, stability, or computational cost.
- **Narrow the disruption-generalization claim** if gains occur only at seen
  locations/severities or disappear under the held-out demand evaluation.

Negative and null outcomes remain reportable evidence about when graph
coordination is unnecessary, ineffective, or harmful.

## Routing gate and scope fallback

| Scope | Classification |
|---|---|
| Signal-control substrate | `CORE` |
| Signal control under localized disruption | `CORE` |
| Signal plus routing coordination | `CONDITIONAL` |
| Full multi-timescale graph MARL | `STRETCH` |

Routing remains disabled for B0–B3 and T0. Its gate may open only after the
signal-only T0 comparison is frozen and interpreted, a residual failure is
plausibly attributable to route allocation, the incremental comparison is
computationally feasible, and a documented review approves the expansion.

If opened, routing must be tested incrementally as T0 versus uncoupled R0 versus
coordinated T1. If the gate does not open or routing fails, the scientifically
strong fallback is the disruption-aware graph signal-control experiment and
its held-out-location result, including a negative result for capacity
conditioning.

## First five empirical milestones

| Milestone | Question answered |
|---|---|
| 1. Validate and select the smallest multi-intersection SUMO network | Is the network deterministic, signal-safe, reachable under partial capacity loss, and large enough to provide distinct disruption zones? A single intersection may be used only as a tooling smoke test. |
| 2. Run one deterministic B0 fixed-time baseline | Do one versioned normal scenario and one versioned capacity-reduction scenario terminate with complete accounting and plausible traffic behavior? |
| 3. Validate metrics and reproducibility | Do repeated baseline-only runs reconcile scheduled departures, actual departures, arrivals, unfinished classifications, queue/wait integrals, timing, raw outputs, and provenance? |
| 4. Establish B1 independent RL | Can a seeded controller train, checkpoint, reload, and evaluate without data leakage or silent failures? |
| 5. Establish the first B2 static-graph baseline | Is graph message passing reproducible under matched state, reward, actions, budget, and scenarios, providing a trustworthy precursor to B3 and T0? |

No treatment is executed in this five-step publication checkpoint.

## Change control and unresolved decisions

The following are intentionally unresolved in v1 and must not be invented:

- numerical δ and equivalence margin;
- confirmatory inferential procedure, uncertainty level, and the exact
  sufficiently-precise decision boundary;
- throughput and unfinished-trip tolerances;
- recovery-envelope construction and sustained-window duration;
- experiment horizon and clearance-window duration;
- final training and evaluation seed counts;
- exact capacity severities and physical split locations;
- held-out demand family;
- smallest research network and canonical execution environment;
- treatment architecture beyond the causal mechanism boundary; and
- routing activation threshold.

Each later resolution must be justified, versioned, and frozen before the
corresponding confirmatory treatment evidence is observed. Any revision after
treatment evidence must identify the reason and classify affected analyses as
exploratory unless a new untouched confirmatory set is established.

## Immediate next task

`RUN_ONE_DETERMINISTIC_FIXED_TIME_SUMO_BASELINE_ON_THE_SMALLEST_SELECTED_NETWORK_WITH_A_VERSIONED_SCENARIO_SEED_AND_METRIC_RECORD`

This task is recorded but was not executed when this charter was published.
