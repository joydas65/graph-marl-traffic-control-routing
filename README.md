# Graph MARL Traffic Control and Routing

Research repository for Joy Das's M.Tech dissertation on graph-based multi-agent reinforcement learning for coordinated traffic-signal control and dynamic vehicle routing under traffic disruptions.

The repository begins from Shreya Salmalge's single-intersection DQN/SUMO prototype and will record the full research progression: baseline repair, GCQN/GCAC reproduction, disruption-aware graph modelling, two-timescale signal-and-routing control, ablations, and final evaluation.

## Provenance

- Upstream repository: <https://github.com/Shreya-Salmalge/Traffic-Light-Control-using-DQN>
- Upstream commit inherited: `dab14cd6deac66a9116bf85fd40003b6ca2ec451`
- Preservation tag: `baseline-shreya-dqn-original`
- `origin`: <https://github.com/joydas65/graph-marl-traffic-control-routing>
- `upstream`: Shreya Salmalge's repository above

The preservation tag points to the unmodified upstream state. All dissertation changes begin after that point and must retain clear attribution.

## Current status

The inherited code is a Level-0 learning baseline: one DQN controls one four-arm SUMO intersection. It is not the multi-intersection GCQN/GCAC implementation from the 2025 Salmalge-Bhatnagar paper and is not yet a trustworthy experimental baseline. Known blockers include an unregistered PyTorch hidden-layer list, a broken testing import/API, incompatible training and testing observations, incomplete seeding, and missing dependency and result specifications.

No scientific result should be claimed until the repaired implementation passes the reproduction acceptance criteria documented in [`docs/research/baseline-audit.md`](docs/research/baseline-audit.md).

## Research progression

1. Preserve and audit the inherited DQN baseline.
2. Repair it and establish deterministic, tested reproduction.
3. Reproduce or faithfully re-establish the paper's GCQN/GCAC baselines.
4. Build multi-intersection graph environments and reproducible disruptions.
5. Introduce slower routing decisions alongside frequent signal actions.
6. Test the coordination mechanism through ablations and unseen scenarios.
7. Produce a reproducible dissertation and publication-quality evidence package.

## Documentation

- [Project context](docs/project-context.md)
- [Research roadmap](docs/research/roadmap.md)
- [Inherited baseline audit](docs/research/baseline-audit.md)
- [Paper MDP formulation](docs/research/shreya-paper-mdp.md)
- [Monthly effort log](docs/progress/monthly-effort-log.md)
- [Current weekly update](docs/progress/weekly/2026-07-27-to-2026-08-02.md)
- [Mentor guidance](docs/mentoring/2026-07-initial-guidance.md)
- [Foundational literature](docs/references/foundational-literature.md)
- [Decision: one repository for the research history](docs/decisions/0001-single-repository-research-history.md)
- [Documentation index](docs/README.md)

## Research standard

Every reported experiment should identify its question, code commit, configuration, random seeds, simulator and dependency versions, hardware/runtime, raw outputs, aggregate statistics, interpretation, and next decision. Failed and negative experiments are retained when they inform the research.

## Licence status

The upstream repository does not currently declare a licence. Reuse and redistribution terms must be confirmed with the upstream author before broader publication or release. This repository therefore records provenance but does not assert new rights over the inherited code.
