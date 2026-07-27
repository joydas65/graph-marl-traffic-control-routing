# Foundational Literature and Reading Priorities

## Direct research lineage

### Prashanth and Bhatnagar, 2011

Prashanth L. A. and Shalabh Bhatnagar, “Reinforcement Learning With Function Approximation for Traffic Signal Control,” *IEEE Transactions on Intelligent Transportation Systems*, 12(2), 412-421, 2011. DOI: `10.1109/TITS.2010.2091408`.

**Relevant ideas:** discounted-cost MDP formulation, queue and elapsed red-waiting state, function approximation, signal timing, and starvation awareness.

**Dissertation use:** foundational justification for the state/reward lineage and for treating long waits as more than average congestion.

### Prabuchandran, An, and Bhatnagar, 2014

K. J. Prabuchandran, H. K. An, and S. Bhatnagar, “Multi-Agent Reinforcement Learning for Traffic Signal Control,” *IEEE Intelligent Transportation Systems Conference*, 2014.

**Relevant ideas:** distributed multi-intersection control and the transition from centralised formulations to multi-agent learning.

**Dissertation use:** conceptual bridge between the 2011 central/function-approximation work and graph-coordinated node policies.

### Salmalge and Bhatnagar, 2025

Shreya Salmalge and Shalabh Bhatnagar, “Reinforcement Learning Algorithms with Graph Convolution Networks for Traffic Signal Control,” INTSYS 2024, LNICST 608, printed 2025. DOI: `10.1007/978-3-031-86370-7_12`.

**Relevant ideas:** GCQN and GCAC, graph message passing, node-level phase actions, comparison with central/individual DQN and round-robin control, and multi-intersection scalability.

**Authoritative extension directions:** accidents or temporarily unavailable roads, improved updating without frequent retraining, and possible temporal modelling after graph convolution.

**Dissertation use:** direct inherited baseline and the primary source from which the new problem must clearly extend.

## Algorithmic reading priorities

### DQN foundations

- Bellman optimality and temporal-difference learning
- experience replay
- target networks and Double DQN
- exploration schedules
- terminal transitions
- stability, checkpointing, and deterministic evaluation

### Actor-critic foundations

- policy-gradient objective
- value functions and advantage estimation
- entropy regularisation
- on-policy versus off-policy trade-offs
- multi-agent credit assignment

### Graph learning foundations

- graph convolution/message passing
- node and edge features
- normalised adjacency and self-loops
- locality and receptive fields
- permutation equivariance
- dynamic or masked topology
- oversmoothing and scalability

### Multi-agent reinforcement learning

- independent learners
- parameter sharing
- centralised training with decentralised execution
- non-stationarity
- global versus local rewards
- counterfactual and difference rewards
- cooperative credit assignment

### Hierarchical and multi-timescale control

- options and macro-actions
- semi-Markov decision processes
- asynchronous updates
- hierarchical credit assignment
- timescale separation assumptions
- coordination between routing and signal objectives

## Traffic-simulation reading priorities

- SUMO network, route, detector, and traffic-light definitions
- TraCI stepping and subscriptions
- queue, waiting, delay, throughput, and teleport semantics
- dynamic edge closure, capacity change, and rerouting
- demand generation and train/test scenario separation
- calibration versus synthetic controlled experiments

## Literature-matrix fields

For every candidate paper, record:

- problem and network scale;
- simulator/data;
- state, action, reward, and timing;
- agent/coordination architecture;
- graph construction;
- routing involvement;
- disruption model;
- baselines and ablations;
- seeds/statistics;
- metrics;
- code/data availability;
- limitations and future work; and
- exact relevance to the proposed contribution.

Paper PDFs should not be committed unless their licences explicitly permit redistribution. Store citations and original notes in the repository instead.
