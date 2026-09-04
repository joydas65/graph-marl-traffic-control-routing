# Capacity-Conditioned Graph TSC Novelty Audit — September 2026

## Status and audit boundary

This is a pre-empirical, public-source literature record supporting the
[Dissertation Empirical Research Charter v1](dissertation-empirical-research-charter-v1.md).
It records a bounded audit of relevant scholarly work available through
4 September 2026. Peer-reviewed primary papers were preferred; recent
preprints were included only when they materially affected the collision test.

> No near-duplicate was located in the bounded public-source audit through
> 4 September 2026; this is not proof that no unpublished, unindexed, or later
> work exists.

No capacity-conditioned treatment result existed when this audit and the
charter were frozen. The classifications below are literature assessments, not
empirical claims about the proposed controller.

## Audit method

- **Time boundary:** approximately 2018 through 4 September 2026, with emphasis
  on 2023–2026 work.
- **Discovery sources:** public scholarly search results, DOI-resolving
  publisher records, arXiv, SSRN, and citation leads from the public
  Salmalge–Bhatnagar lineage paper and the closest located studies.
- **Query families:** graph/GNN multi-intersection signal control; learned or
  changing communication graphs; incidents, blockages, lane closures, work
  zones, and capacity reductions; OOD/transfer and unseen disruptions;
  capacity-aware graph computation; and joint signal/routing MARL.
- **Inclusion rule:** retain primary work materially overlapping at least one
  of the six candidate elements, prioritizing peer-reviewed control papers.
  Highly relevant preprints were retained for collision testing and are marked
  as such. Prediction and routing papers were retained only where they bound a
  claimed mechanism or scope choice.
- **Screening rule:** a near-duplicate required all six elements in one study.
  Generic OOD, learned traffic-state attention, simulator-side closure, or a
  capacity observation did not count as the proposed mechanism or location
  split.
- **Evidence rule:** conclusions were based on accessible primary text and
  publisher metadata; unavailable details were not treated as positive overlap.

The audit is reproducible at the level of its date, source classes, query
families, inclusion boundary, and collision rule. It is not a systematic-review
claim and reports no exhaustive search-result count.

## Approved research question

> Under temporary localized road-capacity reductions, does conditioning
> inter-agent graph communication on current link capacity and availability
> reduce fixed-horizon door-to-door trip-time burden at disruption locations
> withheld from training, relative to an otherwise matched static-graph signal
> controller receiving the same local disruption observations?

## Research claim boundary

### Not novel by itself

- GNN or MARL traffic-signal control;
- learned attention or dynamic-graph terminology;
- disruption-aware or resilient traffic-signal control;
- out-of-distribution traffic-signal control;
- routing combined with signal control; or
- adding capacity or availability to an observation vector.

### Candidate contribution

The candidate contribution is the conjunction of:

1. localized temporary road-capacity reduction;
2. residual capacity or availability directly governing message admission or
   weighting;
3. graph multi-agent signal control;
4. a matched disruption-informed static-graph comparator;
5. evaluation at physical disruption locations withheld from training; and
6. evidence about congestion propagation and recovery.

Algorithmic novelty is assessed as moderate. The evaluation and methodological
contributions currently appear stronger because they isolate one physical
communication mechanism under a disjoint location split and a tightly matched
comparison.

## Literature families

| Family | Representative primary work | Boundary established by the literature |
|---|---|---|
| Graph/GNN multi-intersection signal control | [CoLight](https://doi.org/10.1145/3357384.3357902), [IG-RL](https://doi.org/10.1109/TITS.2021.3070835), [Salmalge and Bhatnagar](https://doi.org/10.1007/978-3-031-86370-7_12), [CoevoMARL](https://doi.org/10.1109/TITS.2024.3410023) | Graph coordination and scalable multi-intersection learning are established contributions. The Salmalge–Bhatnagar work is the dissertation's public static-GCN lineage, not evidence for the proposed disruption treatment. |
| Dynamically weighted or changing communication | CoLight, CoevoMARL, [DSMEL](https://doi.org/10.1016/j.conengprac.2025.106606), [SANIS-MARL](https://doi.org/10.1038/s41598-026-65802-z), [HC-STGRL](https://doi.org/10.3389/frai.2026.1891950) (accepted; final formatted version pending at the cutoff) | Learned attention, state-dependent weights, latent relations, and adaptive edge selection already exist. “Dynamic graph” is therefore too broad a novelty claim. |
| Signal control under incidents, closures, and capacity loss | [Korecki et al.](https://doi.org/10.1109/ACCESS.2023.3266644), [Zeinaly et al.](https://doi.org/10.3390/su15021329), [T-REX](https://arxiv.org/abs/2506.13836), [Yousfi et al.](https://doi.org/10.2139/ssrn.6644234), [Ouyang et al.](https://doi.org/10.3390/su18115561), [Afriyie et al.](https://doi.org/10.3390/futuretransp6040172), [Xiang et al.](https://doi.org/10.1016/j.eng.2026.05.016) | Disruption-aware control, stress testing, spillback, and recovery metrics are increasingly well covered. |
| OOD, generalization, and transfer | IG-RL, [TransferLight](https://arxiv.org/abs/2412.09719), [Braun](https://arxiv.org/abs/2607.21831), [Yang and Zeng](https://doi.org/10.1016/j.eswa.2026.132707) | Unseen demand, geometry, traffic regimes, and networks are established targets. They are not equivalent to a disjoint physical disruption-location test. |
| Capacity-aware graph mechanisms | [RCDGCN](https://doi.org/10.1109/ITSC58415.2024.10920133), DSMEL, Yousfi et al., [Cao et al.](https://doi.org/10.1038/s41598-026-60941-9) | Capacity-driven graph computation exists in traffic prediction, and capacity can appear in graph-controller state. The audit did not locate capacity directly controlling inter-agent communication in multi-agent signal control. |
| Joint signal control and routing | [Gao et al.](https://doi.org/10.6040/j.issn.1672-3961.0.2024.065), Xiang et al. | Joint route/signal learning and traveler-response coupling exist, but routing is not necessary to distinguish the present signal-communication question. |

## Closest novelty threats

| Work | Direct or partial overlap | Missing part of the six-element conjunction |
|---|---|---|
| [Yousfi et al., 2026 preprint](https://doi.org/10.2139/ssrn.6644234) | GATv2 multi-agent signal control, nominal training, temporary blockages/capacity reductions, severe structural stress, and explicit recovery metrics | Graph attention responds indirectly to traffic embeddings rather than physical residual capacity; no matched disruption-time static graph; no declared train-location versus disjoint test-location partition |
| [DSMEL, 2025](https://doi.org/10.1016/j.conengprac.2025.106606) | Dynamic heterogeneous graph signal control and accident/weather stress tests | Edges adapt to learned traffic-feature correlations, not explicit physical capacity; no held-out disruption-location protocol; no exact matched static comparator under the proposed observation contract |
| [RCDGCN, 2024](https://doi.org/10.1109/ITSC58415.2024.10920133) | Static and dynamic roadway-capacity factors directly influence graph convolution, with ablation and weight analysis | Solves network traffic prediction rather than multi-agent signal control; no matched signal-controller experiment or held-out disruption-location evaluation |
| [T-REX, 2025 preprint](https://arxiv.org/abs/2506.13836) | Reproducible incident scenarios with blocked lanes, probabilistic rerouting, propagation, and robustness comparisons | Benchmark methods differ architecturally; no capacity-conditioned graph operator and no disjoint physical incident-location split |
| [Ouyang et al., 2026](https://doi.org/10.3390/su18115561) | Perturbation gradients, shared-interface learned comparisons, congestion-growth observables, and cross-network validation | Centralized non-graph controller; no capacity-conditioned messages or held-out location split |
| [Xiang et al., 2026](https://doi.org/10.1016/j.eng.2026.05.016) (in press; journal pre-proof at the cutoff) | Several capacity-loss severities and spatial patterns, traveler adaptation, resilience loss, and recovery | No learned inter-agent graph communication and no matched static/dynamic graph contrast |
| [Zeinaly et al., 2023](https://doi.org/10.3390/su15021329) | Accident-aware control tested at changed accident position/direction without retraining | One intersection; no graph communication, matched graph comparator, or network-level held-out link split |
| [Korecki et al., 2023](https://doi.org/10.1109/ACCESS.2023.3266644) | Controlled link-removal disruption benchmark across signal-control approaches | No physical-capacity-conditioned graph communication or exact location-generalization design |

The most direct thematic collision is the 2026 Yousfi preprint. The closest
peer-reviewed dynamic-graph collision is DSMEL, while RCDGCN is the closest
precedent for capacity entering graph computation. None performs the complete
proposed experiment.

`STRONGEST_NOVELTY_THREATS=Yousfi_et_al._2026;_Xiang_et_al._2026;_Ouyang_et_al._2026`

DSMEL and RCDGCN remain the closest component-level precedents for dynamic
graph signal control and capacity-driven graph computation, respectively.

## Dynamic-graph distinction

The reviewed literature uses “dynamic graph” for several different mechanisms:

1. learned attention over a fixed road-neighbor graph, as in CoLight,
   SANIS-MARL, HC-STGRL, and Yousfi et al.;
2. traffic-state-dependent or learned latent relations, as in CoevoMARL and
   DSMEL;
3. simulator-side physical topology or capacity changes, which need not alter
   the controller's communication graph;
4. heterogeneous graph reconstruction across intersections, lanes, movements,
   phases, sensors, or vehicles;
5. graph structures that vary between networks for inductive transfer; and
6. physical roadway-capacity-conditioned computation, demonstrated most
   directly by RCDGCN for prediction rather than control.

The dissertation-specific distinction survives only if the physical link
condition directly controls communication:

> physical link condition → communication mask/weight → received neighbor
> representation → signal action

Capacity merely appearing in an observation is insufficient. An unconstrained
attention layer that might learn a capacity response is also not equivalent to
an explicit capacity/availability-conditioned operator.

`CAPACITY_CONDITIONED_COMMUNICATION_DISTINCTIVENESS=SUPPORTED`

## Held-out disruption-location gap

Unseen demand and unseen-network evaluation are relatively common in transfer
work. Multiple disruption severities and patterns are also appearing in recent
resilience studies. Explicit physical-location generalization remains much
rarer.

Zeinaly et al. partially address changed accident position within one
intersection. Yousfi et al. expose a nominally trained controller to unseen
blockages, but do not isolate location by training on one declared disruption
set and testing on a disjoint set. T-REX randomizes incidents without reporting
the proposed physical-location partition. The audit located no graph-MARL study
that combines that partition with the matched communication comparison.

`HELD_OUT_DISRUPTION_LOCATION_GAP=SUPPORTED`

## Matched-comparator value

Most close studies compare controllers that differ simultaneously in model
class, observations, objective, size, or training procedure. Component
ablations in DSMEL, Yousfi et al., and Ouyang et al. improve attribution, but do
not provide the exact proposed contrast.

The primary comparison must hold every non-treatment architectural component
and parameterization, non-communication observations, local disruption
observations, reward, action space, training budget, and paired scenario draws
fixed. Only the mapping from physical capacity or availability to the
communication operator should differ. This is high methodological value, not a
claim of standalone algorithmic novelty.

`MATCHED_STATIC_GRAPH_COMPARATOR_VALUE=HIGH`

## Mechanism-evidence gap

A broad claim that earlier work lacks propagation or recovery analysis would be
incorrect. Yousfi et al. report degradation and recovery quantities; Ouyang et
al. analyze congestion growth and instability; Afriyie et al. examine
spillback and dissipation; Xiang et al. use a resilience-area measure; and
SANIS-MARL visualizes attention associated with backward congestion waves.

The narrower gap is supported: the audit located no matched signal-control
study that causally connects physical-capacity-conditioned messages to
graph-hop queue burden, recovery, or burden displacement using message
masking/shuffling or a related intervention. Recovery time by itself would not
establish the proposed mechanism.

`MECHANISM_EVIDENCE_GAP=SUPPORTED`

## Novelty decomposition

| Contribution type | Assessment | Reason |
|---|---|---|
| Algorithmic | `MODERATE` | Dynamic attention is established and capacity-driven graph computation exists in prediction; the signal-control operator remains distinct but conceptually incremental. |
| Evaluation | `STRONG` | The disjoint disruption-location split combined with fixed-horizon trip burden and a matched static graph was not located. |
| Methodological | `STRONG` | Matched ablations, frozen failure rules, unfinished-trip accounting, paired scenarios, and causal diagnostics substantially improve attribution. |
| Transportation insight | `MODERATE` | The experiment may reveal where coordination helps, fails, or relocates congestion, but that insight must be demonstrated rather than assumed. |

## Collision-test outcome

The active collision search required one paper to combine localized temporary
capacity loss, capacity-conditioned inter-agent communication, graph MARL
signal control, a matched disruption-informed static graph, held-out physical
disruption locations, and propagation/recovery mechanism evidence. No reviewed
paper satisfied all six.

`NEAR_DUPLICATE_PRIOR_WORK_FOUND=NO`

This result supports continuing the question; it does not support claims of
absolute, world-first, or proven novelty.

## Research decisions

- `RESEARCH_QUESTION_ACTION=KEEP_CURRENT_RQ`
- `CENTRAL_HYPOTHESIS_STATUS=KEEP`
- `ROUTING_CORE_STATUS=KEEP_CONDITIONAL`

The question already names the distinctions that survived the audit. The
central hypothesis remains falsifiable because the literature does not
establish that the treatment outperforms its matched comparator. Routing stays
outside the core because it would alter traffic assignment and weaken
attribution to the communication mechanism.

## Publication framing

- **Intelligent transportation systems:** credible traffic-control baselines,
  operationally meaningful disruptions, multiple networks where feasible,
  complete-trip accounting, and reproducible results would be expected.
- **Transportation systems and control:** defensible capacity-loss modeling,
  uncertainty, spillback and recovery analysis, and separation of local relief
  from network-wide burden would be central.
- **Applied multi-agent reinforcement learning:** matched communication
  ablations, frozen budgets and seeds, held-out-location evaluation, and
  robustness to failed runs would be expected.
- **Graph learning for networked control:** a precise capacity-to-edge operator,
  comparison with static and learned-attention alternatives, message
  interventions, and graph-hop diagnostics would be expected.

These are plausible research communities, not acceptance predictions.

## PhD research framing

The strongest research principle for future academic discussion is:

> When a physical transportation network temporarily loses service capacity,
> coordination should respect the changed service structure rather than blindly
> preserve nominal communication relationships.

This principle is not proven. Its value depends on matched experiments,
held-out-location generalization, statistical uncertainty, mechanism
diagnostics, and a disciplined interpretation of positive, negative, and null
outcomes. A result showing when capacity conditioning is unnecessary or harmful
would remain scientifically useful if produced under the frozen design.

`PHD_NOVELTY_POSITIONING_RESOLVED=YES`

## Bounded findings

- `CAPACITY_CONDITIONED_COMMUNICATION_DISTINCTIVENESS=SUPPORTED`
- `HELD_OUT_DISRUPTION_LOCATION_GAP=SUPPORTED`
- `MATCHED_STATIC_GRAPH_COMPARATOR_VALUE=HIGH`
- `MECHANISM_EVIDENCE_GAP=SUPPORTED`
- `NEAR_DUPLICATE_PRIOR_WORK_FOUND=NO`
- `RESEARCH_QUESTION_ACTION=KEEP_CURRENT_RQ`
- `CENTRAL_HYPOTHESIS_STATUS=KEEP`
- `ROUTING_CORE_STATUS=KEEP_CONDITIONAL`

## Primary scholarly references

1. Wei, H., et al. (2019). [CoLight: Learning Network-level Cooperation for Traffic Signal Control](https://doi.org/10.1145/3357384.3357902).
2. Devailly, F.-X., Larocque, D., and Charlin, L. (2022; online 2021). [IG-RL: Inductive Graph Reinforcement Learning for Massive-Scale Traffic Signal Control](https://doi.org/10.1109/TITS.2021.3070835).
3. Salmalge, S., and Bhatnagar, S. (2025). [Reinforcement Learning Algorithms with Graph Convolution Networks for Traffic Signal Control](https://doi.org/10.1007/978-3-031-86370-7_12).
4. Korecki, M., Dailisan, D., and Helbing, D. (2023). [How Well Do Reinforcement Learning Approaches Cope With Disruptions? The Case of Traffic Signal Control](https://doi.org/10.1109/ACCESS.2023.3266644).
5. Zeinaly, Z., Sojoodi, M., and Bolouki, S. (2023). [A Resilient Intelligent Traffic Signal Control Scheme for Accident Scenario at Intersections via Deep Reinforcement Learning](https://doi.org/10.3390/su15021329).
6. Chen, W., et al. (2024). [Learning Multi-Intersection Traffic Signal Control via Coevolutionary Multi-Agent Reinforcement Learning](https://doi.org/10.1109/TITS.2024.3410023).
7. Bian, Z., et al. (2024). [Informed Along the Road: Roadway Capacity Driven Graph Convolution Network for Network-Wide Traffic Prediction](https://doi.org/10.1109/ITSC58415.2024.10920133).
8. Schmidt, J., et al. (2024). [TransferLight: Zero-Shot Traffic Signal Control on any Road-Network](https://arxiv.org/abs/2412.09719).
9. Ye, B.-L., et al. (2025). [Multi-intersection traffic signal control based on dynamic spatiotemporal memory enhanced learning](https://doi.org/10.1016/j.conengprac.2025.106606).
10. Nguyen, D. V. A., et al. (2025). [Robustness of Reinforcement Learning-Based Traffic Signal Control under Incidents: A Comparative Study](https://arxiv.org/abs/2506.13836).
11. Yousfi, W., Slama, R., and Laharotte, P.-A. (2026). [Traffic Signal Control with Extended Perception for Enhanced Robustness and Resilience Using Graph Attention and Temporal Encoders](https://doi.org/10.2139/ssrn.6644234).
12. Ouyang, Z., et al. (2026). [Transition-Sensitive Congestion Dynamics in Heterogeneous Urban Traffic Networks Under Coordinated Reinforcement Learning](https://doi.org/10.3390/su18115561).
13. Afriyie, I., et al. (2026). [Safety-Aware Reinforcement Learning Model for Adaptive Traffic Signal Optimization in Work Zone Environments](https://doi.org/10.3390/futuretransp6040172).
14. Xiang, Q., et al. (2026). [Traffic Signal Control with Deep Reinforcement Learning Toward Enhanced Resilience of Urban Road Networks](https://doi.org/10.1016/j.eng.2026.05.016). *Engineering*. Available online 12 June 2026; in press, journal pre-proof as of the 4 September 2026 audit cutoff.
15. Zhang, Y., et al. (2026). [Distributed Multi-Agent Reinforcement Learning with Neighborhood-Aware Spatio-Temporal Coordination for Traffic Network Signal Control](https://doi.org/10.1038/s41598-026-65802-z).
16. Braun, B. (2026). [A Graph-Based Control Interface for Traffic Signals on Heterogeneous Road Networks](https://arxiv.org/abs/2607.21831). *arXiv* preprint arXiv:2607.21831 (submitted 23 July 2026).
17. Yang, S., and Zeng, Z. (2026). [Heterogeneous graph distributional reinforcement learning for out-of-distribution traffic signal control](https://doi.org/10.1016/j.eswa.2026.132707). *Expert Systems with Applications*, 325, Article 132707.
18. Cao, S., Zhang, X., Li, W., and Sun, P. (2026). [Emergency vehicle signal priority control method for arterial intersections in an intelligent connected environment](https://doi.org/10.1038/s41598-026-60941-9). *Scientific Reports*, 16, Article 25112.
19. Gao, J., Liao, Z., Liu, Y., and Zhao, Y. (2025). [Hierarchical multi-agent reinforcement learning based route guidance method combining personalization and signal control](https://doi.org/10.6040/j.issn.1672-3961.0.2024.065). *Journal of Shandong University (Engineering Science)*, 55(3), 34–45.
20. Mohita; Sidak Deep Singh; Subitha D; and Kavitha J. C. (2026). [Beyond Static Snapshots: Gated Recurrent Units and Graph Attention Networks for Smarter Multi-Agent Traffic Control](https://doi.org/10.3389/frai.2026.1891950). *Frontiers in Artificial Intelligence*, 9. Accepted 24 August 2026; final formatted version pending as of the 4 September 2026 audit cutoff.
