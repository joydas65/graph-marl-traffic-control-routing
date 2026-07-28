# MDP Formulation of the Salmalge-Bhatnagar Traffic-Signal-Control Paper

## Purpose and source boundary

This document formalises the MDP described in Shreya Salmalge and Shalabh Bhatnagar, “Reinforcement Learning Algorithms with Graph Convolution Networks for Traffic Signal Control.” It separates the mathematical problem from model architecture and records ambiguities that require code or mentor confirmation.

## 1. Road network and controlled junctions

Let the road network be a graph

`G = (V, E)`,

where junctions are nodes and roads are edges. Let `p = |V|` be the total number of junctions and let `m <= p` be the number of signal-controlled junctions. A junction has at most `k` incoming lanes.

The graph is part of the environment structure. For graph models, it is also supplied to the function approximator through an adjacency matrix with self-loops.

## 2. Decision time and traffic-light cycle

Actions are selected at decision instants

`t_n = nT`, for `n = 0, 1, 2, ...`,

where `T = T_g + T_y` is one signal-control cycle. In the experiments:

- green duration `T_g = 10` seconds;
- yellow duration `T_y = 4` seconds; and
- nominal decision interval `T = 14` seconds.

When the selected phase changes, the old phase receives its four-second yellow transition before the new green. If the same phase is selected again, that green continues through the interval that would otherwise be yellow.

## 3. State space

For incoming lane `j` at junction `i` and decision time `t`, define:

- `q_j^i(t)`: queue length on the lane; and
- `w_j^i(t)`: maximum elapsed time for which a vehicle has waited on that lane since its signal became red.

The elapsed-time feature is zero when the lane is green or no vehicle is waiting. The unaggregated traffic state is the collection of all queue and elapsed-time values over incoming lanes and controlled junctions.

### State aggregation

The paper maps queue and elapsed time to coarse features using thresholds `L_1`, `L_2`, and `T_1`:

`sigma_q(q) = 0` when `q < L_1`, `0.5` when `L_1 <= q <= L_2`, and `1` when `q > L_2`.

`sigma_w(w) = 0` when `w < T_1`, and `1` otherwise.

The reported experimental thresholds are:

- `L_1 = 7 m`;
- `L_2 = 15 m`; and
- `T_1 = 13 s`.

For a graph model, the input is a node-feature matrix

`X_t in R^(p x 2k)`,

where a node row contains aggregated queue and elapsed-time features for up to `k` incoming lanes. The graph network also consumes the road-network adjacency structure.

### Markov limitation

The authors formulate this as an MDP, but the coarse observation omits arrival processes, detailed vehicle positions, speeds, signal history beyond elapsed waiting, and downstream occupancy. It is therefore best understood as an aggregated state intended to approximate the information required for Markov control. Whether it is sufficiently Markov is an empirical modelling assumption.

## 4. Action space

At each controlled junction `i`, an action `a_i(t)` selects one feasible green-phase pattern. The experiments use four phase choices per controlled junction.

The network action is

`a_t = (a_1(t), ..., a_m(t))`.

How this vector is represented depends on the controller:

- **Central DQN:** treats the complete vector as one joint action. With four choices at each of `m` junctions, the number of joint actions is `4^m`.
- **Individual DQN:** each junction selects its own action from four choices using a separate local network.
- **GCQN:** produces per-node Q-values and selects the highest-valued phase at each controlled junction.
- **GCAC:** the graph actor produces a categorical distribution over phases at every controlled junction and samples during training.

Only traffic-safe phase combinations are exposed as the four actions. The theoretical section assumes all defined actions are feasible in every state.

## 5. Transition dynamics

The transition kernel can be written as

`P(s_(t+T) | s_t, a_t)`.

It is induced by vehicle arrivals, routes, car-following and lane-changing behaviour, signal transitions, and network topology inside SUMO. The algorithms are model-free: they do not learn or require an explicit analytical form of `P`.

Demand is stochastic through randomly generated source and destination roads. Episodes use 1,000 vehicles on the 2x2 grid and 1,500 on Modified Sioux Falls.

## 6. Reward and cost

The controller minimises congestion cost or, equivalently, maximises its negative reward. At controlled junction `i`:

`r_i(t) = -[alpha * sum_j q_j^i(t) + beta * sum_j w_j^i(t)]`.

The experiments set

`alpha = beta = 0.5`.

The elapsed-waiting component acts as a starvation/fairness mechanism: even a lane with a small queue becomes costly if it remains red for too long.

- The central DQN uses a network-level scalar reward obtained from congestion across junctions.
- GCQN and GCAC use a reward vector with one component per node; node losses are summed during optimisation.
- Non-signal nodes contribute zero control loss.

This is not the same reward as the public single-junction repository, which uses the change in total waiting plus the change in queue between consecutive decisions.

## 7. Objective

For discount factor `gamma in (0,1)`, the theoretical objective is to maximise expected discounted return:

`J(pi) = E_pi[sum_(n=0)^infinity gamma^n r_(t_n)]`.

The experiments use `gamma = 0.75` and finite episodes. An episode ends when all vehicles reach their destinations or after 5,400 simulation seconds.

For graph methods, maximising the sum of node returns corresponds to minimising overall network congestion while using local reward signals for learning.

## 8. Policies and value functions

### DQN and GCQN

Training uses epsilon-greedy exploration. The greedy policy selects the action with maximum estimated Q-value. A periodically updated target network supplies bootstrap targets.

For GCQN node `i`, a one-step target has the form

`y_i(t) = r_i(t) + gamma * max_j Q_target(i, j | s_(t+T))`.

The squared node losses are summed across controlled nodes and back-propagated through graph-convolution layers. A `K`-layer GCN allows a node decision to depend on features up to `K` hops away.

### GCAC

The graph actor represents a per-node categorical policy `pi_i(a | s)`. The graph critic estimates a per-node state value `V_i(s)`. The paper defines a one-step advantage from the local reward and value change, then:

- minimises squared advantage for the critic; and
- minimises negative log action probability multiplied by advantage for the actor.

The printed GCAC formula should be checked against the original code because the displayed one-step return does not visibly include `gamma`, despite the discounted MDP definition using it.

## 9. Experimental instantiations

### 2x2 grid

- 12 graph nodes, four signal-controlled junctions.
- Eight incoming lanes per controlled junction.
- Graph input shape `12 x 16`.
- GCQN output shape `12 x 4`.
- Central DQN input size 64 and output size `4^4 = 256`.

### Modified Sioux Falls

- 31 graph nodes, 11 signal-controlled junctions.
- Graph input shape `31 x 16`.
- Graph output shape `31 x 4`.
- Central joint DQN is omitted because `4^11` actions are impractical.

## 10. Formal tuple

The paper's control problem can be summarised as:

`M = (S, A, P, R, gamma, T)`,

where:

- `S` contains aggregated lane queue and elapsed-wait features; the fixed road graph `G` is structural context supplied to graph function approximators;
- `A` contains one feasible phase choice per controlled junction;
- `P` is the unknown SUMO traffic transition kernel over a 14-second control cycle;
- `R` is the negative equally weighted queue-and-elapsed-wait cost;
- `gamma = 0.75`; and
- `T` defines the 10-second green and 4-second yellow control timing.

## 11. What Joy must be able to explain

1. Why elapsed red waiting provides a limited fairness mechanism.
2. Why `4^m` makes central DQN unsuitable as `m` grows.
3. Why individual DQNs lose spatial coordination.
4. How GCN message passing changes the information available to a node action.
5. Why a coarse state may violate the strict Markov assumption.
6. Why graph architecture is not itself a new MDP.
7. How the paper MDP differs from the public DQN repository.
8. Which variables must be extended to introduce disruptions and routing.

## 12. Extension points for the dissertation

The dissertation must extend the tuple rather than only add a model layer:

- augment state with edge availability, capacity, incident severity, downstream congestion, and routing context;
- constrain actions through topology and safety masks;
- add slower routing actions or options;
- define transition timing for asynchronous signal and routing decisions;
- define a coordination reward and credit-assignment mechanism; and
- evaluate generalisation to unseen incidents and demand.

The appropriate formal framework may become a semi-MDP, hierarchical MDP, or multi-agent partially observable model. That choice should follow explicit assumptions and mentor review.
