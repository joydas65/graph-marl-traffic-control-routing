# Joint Mentor Meeting — 27 July 2026

I met with Arghya Roy Chaudhuri, my primary company mentor, and Shreya Salmalge, my technical co-mentor, to introduce the inherited research and discuss the preparation needed for its reproduction and extension.

Shreya explained the intuition behind the graph representation. Junctions are treated as nodes and their road connections as edges. Graph convolution then allows the decision at a junction to use traffic information from neighbouring junctions instead of considering only its own queues. This provides a middle ground between a central DQN, whose joint action space grows exponentially with the number of signals, and completely independent DQNs, which do not naturally coordinate through neighbouring congestion.

Arghya explored the reasoning behind the RL and graph choices through several technical questions. The discussion made it clear to me that I need a stronger first-principles understanding of reinforcement learning before I can defend the formulation or evaluate an extension rigorously. The recommendation was to study Sutton and Barto's *Reinforcement Learning: An Introduction* thoroughly rather than prepare isolated answers. At the same time, the reading should remain connected to code, equations, and reproducible experiments so that theoretical learning and visible project progress develop together.

I did not capture the exact wording of Arghya's questions during the call. I have therefore recorded the themes in the [research question bank](../learning/question-bank.md) without presenting them as quotations. Future mentor questions will be written down as asked, together with my initial response, the corrected explanation, and supporting evidence.

## Repository position clarified after the meeting

Shreya's public `Traffic-Light-Control-using-DQN` repository contains a single-intersection DQN prototype built with a fully connected network. It does not contain the graph-convolution layers, GCQN or GCAC models, graph actor-critic implementation, $2\times2$ graph experiment, or Modified Sioux Falls experiment described in the paper.

I also inspected the `traffic-signal-control/RL_signals` repository linked from the paper. It is a collection of traffic-signal-control resources, posters, and benchmark material rather than the implementation used for the GCQN/GCAC experiments. The authoritative experimental code and configuration therefore still need to be requested from Shreya.

## What I took away from the meeting

My immediate goal is to build foundations without losing momentum on implementation. I will complete Chapter 1 with an explain-back note, continue through the textbook systematically, and connect each major concept to the traffic problem. In parallel, the public DQN prototype will serve as a Level-0 engineering baseline: I will run it faithfully, document its behaviour, repair reproducibility problems transparently, and compare results without implying that it reproduces the graph paper.

The paper's GCQN/GCAC experiment remains a separate Level-1 milestone. Before claiming that reproduction, I need the original or archived code, network files, configurations, seeds, and expected results. Weekly evidence will include theory learned, code or experiment output, unresolved questions, and the next planned test.

I will contact Prof. Bhatnagar when I have a concrete reproduction or formulation milestone to report, or when a focused academic decision requires his guidance. This should make each update concise and technically useful.
