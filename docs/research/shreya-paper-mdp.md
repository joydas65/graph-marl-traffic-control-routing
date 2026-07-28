# MDP Formulation of the Salmalge-Bhatnagar Traffic-Signal-Control Paper

## Purpose and source boundary

This note formalises the Markov decision process (MDP) described in Shreya Salmalge and Shalabh Bhatnagar, “Reinforcement Learning Algorithms with Graph Convolution Networks for Traffic Signal Control.” It separates the control problem from the neural-network architecture and records the points that still require confirmation from the authors or the original implementation.

## 1. Road network and controlled junctions

Let the road network be the graph

$$
G=(V,E),
$$

where each junction is a node in $V$ and each road connection is an edge in $E$. Let

$$
p=|V|, \qquad m\leq p,
$$

where $p$ is the total number of junctions and $m$ is the number of signal-controlled junctions. Each junction has at most $k$ incoming lanes.

The graph is part of the environment structure. In GCQN and GCAC it is also supplied to the function approximator through an adjacency matrix with self-loops.

## 2. Decision time and traffic-light cycle

The controller selects actions at discrete decision instants

$$
t_n=nT, \qquad n=0,1,2,\ldots,
$$

where a control cycle has duration

$$
T=T_g+T_y.
$$

The experimental values are

$$
T_g=10\ \text{s}, \qquad T_y=4\ \text{s}, \qquad T=14\ \text{s}.
$$

When the selected phase changes, the previous phase receives a four-second yellow transition before the new green phase begins. If the same phase is selected again, that green phase continues through the interval that would otherwise be used for yellow.

## 3. State space

For incoming lane $j$ at junction $i$ and decision time $t$, define

$$
q_j^i(t)=\text{queue length on lane }j,
$$

and

$$
w_j^i(t)=\text{maximum elapsed waiting time on lane }j
$$

since its signal became red. The elapsed-wait feature is zero while the lane is green or when no vehicle is waiting. Before aggregation, the traffic state is the collection of these queue and waiting-time values over all incoming lanes and controlled junctions.

### State aggregation

The paper converts each queue length into a three-level feature:

$$
\sigma_q(q)=
\begin{cases}
0, & q<L_1,\\
0.5, & L_1\leq q\leq L_2,\\
1, & q>L_2.
\end{cases}
$$

Elapsed waiting time is converted into a binary feature:

$$
\sigma_w(w)=
\begin{cases}
0, & w<T_1,\\
1, & w\geq T_1.
\end{cases}
$$

The experimental thresholds are

$$
L_1=7\ \text{m}, \qquad L_2=15\ \text{m}, \qquad T_1=13\ \text{s}.
$$

For a graph-based controller, the node-feature matrix is

$$
X_t\in\mathbb{R}^{p\times 2k}.
$$

Each row represents one junction and contains the aggregated queue and elapsed-wait features for up to $k$ incoming lanes. The graph network consumes both $X_t$ and the road-network adjacency structure.

### Markov limitation

The paper treats this observation as the MDP state. In practice, the coarse representation omits arrival processes, exact vehicle positions and speeds, downstream occupancy, and most of the signal history. Its Markov property is therefore a modelling assumption: the aggregated state is intended to contain enough information for useful control, but it may not be a sufficient statistic of the simulator's underlying state.

## 4. Action space

At controlled junction $i$, the action

$$
a_i(t)\in\mathcal{A}_i
$$

selects one of four feasible green-phase patterns. The complete network action is

$$
\mathbf{a}_t=\bigl(a_1(t),a_2(t),\ldots,a_m(t)\bigr)
\in\mathcal{A}_1\times\cdots\times\mathcal{A}_m.
$$

The way this joint decision is represented depends on the controller:

- **Central DQN:** treats $\mathbf{a}_t$ as one joint action, giving

  $$
  |\mathcal{A}|=4^m.
  $$

- **Individual DQN:** uses a separate local network at each junction, with $|\mathcal{A}_i|=4$.
- **GCQN:** produces four Q-values per controlled node and chooses the phase with the largest value.
- **GCAC:** produces a categorical distribution over the four phases at each controlled node and samples from it during training.

Only traffic-safe phase combinations are exposed as actions. The theoretical formulation assumes that every defined action is feasible whenever it may be selected.

## 5. Transition dynamics

The transition kernel over one control cycle is

$$
P\!\left(s_{t+T}\mid s_t,\mathbf{a}_t\right).
$$

It is induced by vehicle arrivals and routes, car-following and lane-changing behaviour, road topology, and traffic-light transitions inside SUMO. The learning algorithms are model-free, so they do not require an analytical expression for $P$.

Demand is stochastic because source and destination roads are generated randomly. The reported episodes contain 1,000 vehicles on the $2\times2$ grid and 1,500 vehicles on Modified Sioux Falls.

## 6. Reward and congestion cost

The local reward at controlled junction $i$ is the negative of a weighted congestion cost:

$$
r_i(t)
=-
\left[
\alpha\sum_{j=1}^{k_i}q_j^i(t)
+
\beta\sum_{j=1}^{k_i}w_j^i(t)
\right],
$$

where $k_i\leq k$ is the number of incoming lanes at that junction. The experiments use

$$
\alpha=\beta=0.5.
$$

The waiting-time term provides a limited fairness mechanism: a lane becomes increasingly costly if it stays red, even when its queue is not the largest.

For a central controller, a natural network-level reward is

$$
r(t)=\sum_{i=1}^{m}r_i(t).
$$

GCQN and GCAC instead retain the node-level reward vector

$$
\mathbf{r}_t=\bigl(r_1(t),\ldots,r_m(t)\bigr),
$$

and sum node losses during optimisation. Nodes without controllable traffic signals contribute no control loss.

This reward differs from the public single-junction repository, which uses the change in total waiting time plus the change in queue length between consecutive decisions.

## 7. Objective

For a policy $\pi$ and discount factor $\gamma\in(0,1)$, the objective is to maximise expected discounted return:

$$
J(\pi)
=
\mathbb{E}_{\pi}
\left[
\sum_{n=0}^{\infty}\gamma^n r(t_n)
\right].
$$

Equivalently, a node-wise graph controller can maximise

$$
J(\pi)
=
\sum_{i=1}^{m}
\mathbb{E}_{\pi}
\left[
\sum_{n=0}^{\infty}\gamma^n r_i(t_n)
\right].
$$

The experiments use $\gamma=0.75$ and finite episodes. An episode ends when every vehicle reaches its destination or when the simulation reaches 5,400 seconds.

## 8. Policies and value functions

### DQN and GCQN

Training uses $\varepsilon$-greedy exploration. For GCQN node $i$, a standard one-step target is

$$
y_i(t)
=
r_i(t)
+
\gamma\max_{a'\in\mathcal{A}_i}
Q_{\omega^-}^{i}\!\left(s_{t+T},a'\right),
$$

where $\omega^-$ denotes the target-network parameters. The corresponding node-wise temporal-difference loss is

$$
\mathcal{L}_{\mathrm{GCQN}}(\omega)
=
\sum_{i=1}^{m}
\left[
y_i(t)-Q_{\omega}^{i}\!\left(s_t,a_i(t)\right)
\right]^2.
$$

Back-propagation carries this loss through the graph-convolution layers. With $K$ message-passing layers, a node representation can incorporate information from nodes up to $K$ graph hops away.

### GCAC

The graph actor represents a categorical policy $\pi_\theta^i(a\mid s)$ for each controlled node, while the graph critic estimates a node value $V_\phi^i(s)$. The paper's printed one-step advantage appears to be

$$
A_i(t)
=
r_i(t)
+
V_\phi^i(s_{t+T})
-
V_\phi^i(s_t).
$$

A discounted form consistent with the stated MDP would instead be

$$
A_i^{(\gamma)}(t)
=
r_i(t)
+
\gamma V_\phi^i(s_{t+T})
-
V_\phi^i(s_t).
$$

The actor and critic losses can then be written as

$$
\mathcal{L}_{\mathrm{actor}}(\theta)
=
-\sum_{i=1}^{m}
\log \pi_\theta^i\!\left(a_i(t)\mid s_t\right)A_i(t),
$$

and

$$
\mathcal{L}_{\mathrm{critic}}(\phi)
=
\sum_{i=1}^{m}A_i(t)^2.
$$

Whether the implementation used the printed or discounted advantage must be checked against the authors' code, because the displayed equation does not visibly include $\gamma$ even though the MDP definition is discounted.

## 9. Experimental instantiations

### $2\times2$ grid

- 12 graph nodes, including four signal-controlled junctions.
- Eight incoming lanes per controlled junction.
- Graph input: $X_t\in\mathbb{R}^{12\times16}$.
- GCQN output: $Q_t\in\mathbb{R}^{12\times4}$.
- Central DQN input dimension: $64$.
- Central DQN output dimension: $4^4=256$.

### Modified Sioux Falls

- 31 graph nodes, including 11 signal-controlled junctions.
- Graph input: $X_t\in\mathbb{R}^{31\times16}$.
- Graph output: $Q_t\in\mathbb{R}^{31\times4}$.
- Central DQN is omitted because its joint action space would contain $4^{11}=4{,}194{,}304$ actions.

## 10. Complete MDP tuple

The paper's control problem can be summarised as

$$
\mathcal{M}
=
\left(
\mathcal{S},
\mathcal{A},
P,
R,
\gamma,
T
\right),
$$

where:

- $\mathcal{S}$ contains the aggregated lane queue and elapsed-wait features. The fixed graph $G$ is structural context supplied to the graph-based function approximators.
- $\mathcal{A}=\mathcal{A}_1\times\cdots\times\mathcal{A}_m$ contains one feasible signal phase per controlled junction.
- $P(s_{t+T}\mid s_t,\mathbf{a}_t)$ is the unknown SUMO transition kernel over a 14-second control cycle.
- $R$ is the negative, equally weighted queue-and-waiting cost.
- $\gamma=0.75$ is the reported discount factor.
- $T=T_g+T_y=14$ seconds defines the decision interval.

The policy is therefore a mapping

$$
\pi:\mathcal{S}\longrightarrow\Delta(\mathcal{A}),
$$

or, for decentralised graph control, a collection of node policies

$$
\pi_i:\mathcal{S}\longrightarrow\Delta(\mathcal{A}_i),
\qquad i=1,\ldots,m.
$$

## 11. Questions I should be able to answer

After studying this formulation, I should be able to explain why elapsed red waiting supplies a limited fairness signal, why the $4^m$ joint action space prevents central DQN from scaling, and why independent DQNs lose spatial coordination. I should also be able to describe what graph message passing adds to each junction's information, why the aggregated state may not be strictly Markov, and why replacing a dense network with a GCN changes the policy architecture but not the underlying MDP.

I also need to keep the paper formulation separate from the public DQN repository: the two use different network structures, traffic layouts, and rewards. That distinction is essential when I report a baseline reproduction.

## 12. Dissertation extension points

The dissertation must extend the decision problem rather than merely insert another neural-network layer. Likely changes include augmenting the state with road availability, capacity, incident severity, downstream congestion, and routing context; masking infeasible signal or routing actions; adding slower routing decisions; and defining a coordination reward that supports meaningful credit assignment.

Once routing and signal control operate on different timescales, the timing assumptions must be explicit. Depending on how decisions persist and what each agent observes, the appropriate framework may be a semi-MDP, a hierarchical MDP, or a partially observable multi-agent model. That choice should follow a precise problem statement and discussion with the mentors.
