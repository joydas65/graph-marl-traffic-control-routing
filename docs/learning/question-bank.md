# Questions Raised by the Research

This is a working record of the questions I need to answer confidently during mentor discussions. I did not write down Arghya's questions word for word during the meeting on 27 July, so I will not present reconstructed wording as a quotation. Instead, I have recorded the areas that his questions showed I need to understand more deeply. When a question comes up again, I will add its exact wording and the evidence behind my answer.

## What the first joint discussion made me examine

The first group of questions concerns the RL formulation itself. I need to be able to justify why traffic control is a sequential decision problem, what makes the formulation an MDP, and whether the paper's aggregated traffic observation is genuinely Markov. I also need a precise distinction between immediate reward, discounted return, state value, and action value—not just their definitions, but what each one means for a traffic signal.

The discussion also exposed gaps around learning algorithms. I want to be able to derive the Bellman expectation and optimality equations, compare Monte Carlo and temporal-difference learning, and explain on-policy versus off-policy methods. For DQN, I should be ready to explain exploration, replay memory, and the target network, as well as the instability created by combining function approximation, bootstrapping, and off-policy learning. For actor-critic methods, I need to describe separately what the actor, critic, and advantage estimate contribute.

## Questions about the graph formulation

The graph model needs more than an intuitive explanation. I should be able to identify the node features, edges, adjacency matrix, and self-loops in Shreya's formulation, then show what information becomes available after one or more graph-convolution layers. I also need to explain why a central DQN has $4^m$ joint actions for $m$ four-phase junctions, why independent DQNs scale more easily but may fail to coordinate, and how node-level rewards with a summed loss are intended to support cooperative behaviour.

Some questions remain open rather than merely educational. Does a trained GCN generalise when a road is closed or the topology changes? How should unavailable roads and invalid actions be masked? How much message passing is useful before node representations become oversmoothed? Most importantly, what ablation would show that an improvement comes from graph structure rather than simply from a larger network or additional parameters?

## Questions that shape the dissertation

For the proposed extension, I need a rigorous reason for placing signal control and vehicle routing on different timescales. That decision affects whether the problem remains an ordinary MDP or is better described as a semi-MDP, hierarchical MDP, or partially observable multi-agent problem. I also need to decide what information the routing and signal policies exchange, how they receive credit for a shared outcome, and how invalid routing choices are represented after a disruption.

The central research question must eventually be stated more sharply than “combine graph RL, signals, and routing.” I need to identify the testable novelty, define training and held-out incident scenarios, and specify the evidence needed to claim generalisation to unseen disruptions. I should also maintain a useful fallback contribution—such as a reproducible graph signal-control baseline and disruption benchmark—if end-to-end learned routing proves infeasible within the dissertation schedule.

## How I will work through a question

For each important question, I will first try to give a two- or three-sentence answer in plain language. I will then write the relevant definition or equation, connect it to the paper, and locate supporting code or an experiment. Finally, I will record any assumption or unresolved point instead of hiding it behind a confident-sounding answer.

| Date | Question as asked | My first answer | Evidence or corrected answer | Remaining uncertainty |
|---|---|---|---|---|
| 27 Jul 2026 | Exact wording not recorded | — | The themes above were identified from the discussion. | Add the exact question if it is recalled or asked again. |
