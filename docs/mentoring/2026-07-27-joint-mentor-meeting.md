# Joint Mentor Meeting: 27 July 2026

## Participants

- Joy Das
- Arghya Roy Chaudhuri, primary company mentor
- Shreya Salmalge, technical co-mentor

## Purpose

Introduce the inherited research to Arghya, discuss the graph-based traffic-signal-control intuition, and assess the reinforcement-learning foundation required before reproduction and extension.

## Discussion captured

- Shreya explained the central graph intuition: represent junctions as nodes and roads as edges, then use graph convolution to allow a signal decision at one junction to incorporate congestion information from neighbouring junctions.
- The graph approach was contrasted with a central DQN, whose joint action space grows exponentially with the number of controlled intersections, and independent DQNs, which do not naturally coordinate using neighbouring congestion.
- Arghya asked several technical questions to probe the underlying RL and graph reasoning.
- Joy identified that his current RL knowledge is foundational and that deeper command of the theory is required to answer questions precisely.
- The recommended foundation is a thorough reading of Sutton and Barto, *Reinforcement Learning: An Introduction*, across all chapters.
- Theory development must run in parallel with visible reproduction and research progress.

## Important record limitation

The exact wording of Arghya's individual questions was not captured. They must not be reconstructed as quotations. The known themes have been converted into preparation questions in `docs/learning/question-bank.md`; exact questions should be added when Joy recalls or encounters them again.

## Repository clarification after the meeting

- Shreya's public `Traffic-Light-Control-using-DQN` repository contains a single-intersection, fully connected DQN prototype.
- It does not contain GCN layers, GCQN, GCAC, graph actor/critic models, the 2x2 graph environment, or Modified Sioux Falls experiments.
- The repository linked in the paper, `traffic-signal-control/RL_signals`, was inspected and found to be a general resource catalogue containing a README, benchmark image, and posters—not the paper implementation.
- The authoritative GCQN/GCAC experimental code therefore remains unavailable and must be requested from Shreya.

## Decisions

1. Study RL systematically rather than attempting to memorise isolated answers.
2. Pair each theory topic with an equation, implementation, and connection to the traffic problem.
3. Reproduce the public DQN prototype first as a Level-0 engineering and learning baseline.
4. Keep the final GCQN/GCAC paper reproduction as a separate Level-1 milestone.
5. Maintain a question bank and weekly evidence update.

## Actions

- Joy: complete Chapter 1 and write an explain-back note before moving rapidly through later chapters.
- Joy: reconstruct any exact questions he remembers in the question bank.
- Joy/Codex: formalise the MDP from the paper and map it to the public DQN implementation.
- Joy/Codex: begin `baseline/dqn-reproduction` after the repository-foundation commit.
- Joy: ask Shreya for the archived/final GCQN/GCAC code, networks, configurations, seeds, and expected results.
- Joy: provide Prof. Bhatnagar a concise update only after a concrete foundation/reproduction milestone or when a focused academic decision is needed.
