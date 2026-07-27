# Dissertation Project Context

## Identity

- **Student:** Joy Das
- **Programme:** M.Tech. (Online), Artificial Intelligence
- **Project period:** August 2026 to May/June 2027
- **Working title:** *Graph-Based Multi-Agent Reinforcement Learning for Coordinated Traffic Signal Control and Dynamic Vehicle Routing under Traffic Disruptions*
- **Faculty mentor:** Prof. Shalabh Bhatnagar, Department of Computer Science and Automation, IISc Bengaluru
- **Primary company mentor:** Arghya Roy Chaudhuri, Walmart
- **Technical co-mentor:** Shreya Salmalge, Walmart

Only public-safe role information belongs here. Administrative documents and personal identifiers are intentionally excluded.

## Problem statement

Urban traffic networks contain two coupled control problems:

1. traffic signals must react frequently to local and neighbouring congestion; and
2. routing decisions should react more slowly to network-level conditions and disruptions.

The dissertation will study a road system as a directed attributed graph. Intersections are controlled nodes, roads are edges, and observations may contain queues, waiting, speeds, densities, signal state, phase age, capacity, availability, and incident indicators. Signal agents choose safe green phases at a short interval. A routing mechanism chooses aggregate route or path guidance at a slower interval.

The scientific contribution cannot be merely the coexistence of a GNN, multiple agents, and two timescales. It must define how the signal and routing policies coordinate, how asynchronous decisions enter the learning update, and which controlled comparisons isolate the benefit of that mechanism.

## Research lineage

This work extends a sequence of traffic-control research associated with Prof. Bhatnagar:

1. Prashanth and Bhatnagar (2011): function-approximation reinforcement learning for traffic-signal control.
2. Prabuchandran, An, and Bhatnagar (2014): multi-agent reinforcement learning for distributed traffic-signal control.
3. Salmalge and Bhatnagar (2025): GCQN and GCAC for graph-based, multi-intersection signal control.
4. This dissertation: disruption-aware graph coordination plus a slower routing layer.

Prof. Bhatnagar directly advised that the dissertation extend the Salmalge-Bhatnagar work. The paper's stated directions—accidents or temporarily unavailable roads, better updating without frequent retraining, and possible temporal modelling—are therefore important scope anchors.

## Intended formulation

### Environment

- SUMO controlled through TraCI.
- Multi-intersection road graph with controlled traffic lights.
- Reproducible traffic demand and incident scenarios.
- Normal operation plus accidents, closures, capacity reductions, and demand surges.

### Signal layer

- Frequent, safety-constrained phase decisions.
- Graph observations containing local and neighbouring traffic information.
- Shared or coordinated policies to support network scaling.

### Routing layer

- Slower decisions over routes, path sets, OD flows, zones, or aggregate guidance.
- Network-level observations and disruption awareness.
- Explicit interface with the signal layer rather than independent optimisation.

### Candidate learning structure

The proposal anticipates graph neural networks and centralised training with decentralised execution. This is a working direction, not yet a fixed algorithm. The project must compare plausible coordination mechanisms before locking the final method.

## Required evaluation

At minimum, report:

- average and percentile travel time or delay;
- mean, maximum, and percentile queue lengths;
- throughput and unfinished trips;
- accumulated waiting and starvation/tail behaviour;
- disruption recovery time;
- fairness across routes, OD flows, or regions;
- training stability, runtime, and inference cost; and
- uncertainty over multiple seeds.

Evaluation must cover ordinary traffic, seen disruptions, unseen incident locations, unseen demand patterns, and multiple severities. Ablations should isolate graph information, disruption features, routing, timescale separation, and coordination.

## Baseline chain

- **Level 0:** repair and reproduce the inherited single-intersection DQN repository.
- **Level 1:** reproduce the 2025 paper's GCQN/GCAC baselines using the mentor-confirmed authoritative code and configuration.
- **Level 2:** add a tested multi-intersection graph environment and disruption generator.
- **Level 3:** implement the coordinated two-timescale signal-and-routing method.
- **Level 4:** run ablations, generalisation studies, statistical evaluation, and final reporting.

The current fork is Level 0. It must not be represented as the paper's GCQN/GCAC implementation.

## Minimum defensible scope and fallback

The minimum scientific deliverable is disruption-aware graph-based signal control with rigorous reproduction and generalisation tests. If learned joint routing becomes infeasible within the schedule, SUMO-provided dynamic routing may serve as the routing component while the signal-control contribution remains the evaluated research focus. This fallback should be exercised only after a documented gate review with the mentors.

## Current technical status: 27 July 2026

- SUMO 1.27.1, SUMO-GUI, NetEdit, TraCI, and `sumolib` are installed and verified on Apple Silicon macOS.
- The official SUMO quickstart completed successfully in CLI and GUI modes.
- Shreya's repository was audited file by file at commit `dab14cd6deac66a9116bf85fd40003b6ca2ec451`.
- Joy forked it as `joydas65/graph-marl-traffic-control-routing`, cloned it locally, and configured `origin` and `upstream`.
- The untouched baseline is marked locally by annotated tag `baseline-shreya-dqn-original`.
- A one-repository strategy was selected to make the complete progression reviewable over the dissertation period.

## Open questions requiring mentor alignment

1. Is `traffic-signal-control/RL_signals` the authoritative code for the 2025 GCQN/GCAC experiments, and which commit/configuration should be reproduced?
2. What exact research hypothesis should distinguish this dissertation from a system integration exercise?
3. What is the preferred coordination mechanism between signal and routing policies?
4. Which network, traffic distributions, and disruption families are sufficient for the first evaluation gate?
5. Which result would be strong enough to target a workshop, conference, or journal submission?

## Working principles

- Research quality is shown through controlled evidence, not commit count.
- Negative results and failed approaches are recorded when they affect a decision.
- Mentor communication should present a focused question, evidence, interpretation, and requested decision.
- Scope expansion requires a corresponding evaluation plan and schedule trade-off.
- Reproducibility is a deliverable, not post-processing.
