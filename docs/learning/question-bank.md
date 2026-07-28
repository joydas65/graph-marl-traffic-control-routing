# RL and Graph Traffic-Control Question Bank

## How to use this document

For every question raised by a mentor, record the exact wording, the initial answer, the corrected answer, one equation or experiment supporting it, and the remaining uncertainty. Do not present theme-based preparation questions as verbatim mentor questions.

## Questions from the 27 July meeting

The exact wording was not captured. Joy should add recalled questions below rather than guessing.

| Exact question | Initial answer | Corrected answer/evidence | Remaining gap |
|---|---|---|---|
| To be reconstructed by Joy |  |  |  |

## Preparation questions: RL foundations

1. What makes a problem an MDP, and is the aggregated traffic state truly Markov?
2. What is the difference between immediate reward, return, state value, and action value?
3. Why is traffic-signal control a sequential decision problem rather than supervised prediction?
4. What is the Bellman expectation equation versus the Bellman optimality equation?
5. What is the difference between on-policy and off-policy learning?
6. What do Monte Carlo and temporal-difference methods estimate differently?
7. Why are exploration, replay memory, and a target network used in DQN?
8. What is the deadly triad of function approximation, bootstrapping, and off-policy learning?
9. What does an actor learn, what does a critic learn, and what is an advantage estimate?
10. Why are multiple seeds and non-learning baselines necessary before claiming improvement?

## Preparation questions: graph control

1. Why can a fully connected DNN not use road topology as explicitly as a GCN?
2. What are the node features, edges, adjacency matrix, and self-loops in Shreya's formulation?
3. What information is shared after one, two, or more graph-convolution layers?
4. Why does the central DQN action space grow as `4^m` for `m` four-phase junctions?
5. Why can independent DQNs scale yet fail to coordinate?
6. How do node-level rewards and summed losses encourage cooperative behaviour?
7. What is graph oversmoothing, and why did it matter on the small 2x2 experiment?
8. Can a trained GCN generalise to a changed topology or road closure without retraining?
9. How should unavailable roads and invalid signal/routing actions be masked?
10. What evidence would isolate the value of graph message passing from model size alone?

## Preparation questions: proposed dissertation

1. Why should signal control and routing operate at different timescales?
2. Is the resulting process an MDP, semi-MDP, hierarchical MDP, or another formulation?
3. How will routing and signal policies exchange information and receive credit?
4. What is the precise novelty beyond combining existing components?
5. How will unseen incident locations and severities be separated from training?
6. What is the fallback contribution if learned joint routing is not feasible?

## Answer template

### Question

### Short answer

### Definitions and assumptions

### Mathematical explanation

### Connection to Shreya's paper

### Supporting code or experiment

### Limitation or unresolved point
