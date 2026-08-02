# Salmalge-Bhatnagar Paper-to-Code Semantic Map

## Purpose

This document records the public-safe results of a static semantic audit of the private GCQN and GCAC handovers. It asks whether the implementation concepts visible in the handovers correspond to Sections 2.1-3.3 and Algorithms 1-2 of the paper.

This is not a reproduction report. The handovers were read as source text only: they were not imported, installed, trained, or used to execute checkpoints. Every finding below therefore requires runtime verification before it can support a dissertation result.

## Scope

Included:

- MDP state, aggregation, graph, action, phase, reward, replay, and terminal semantics;
- Algorithm 1: GCQN action selection, target, loss, architecture, and updates;
- Algorithm 2: GCAC policy, actor, critic, return, losses, updates, and replay behavior.

Deferred:

- Section 4 experiments;
- Figures 3-5 and Tables 1-2;
- dataset identity and stored-result attribution;
- simulator or dependency installation;
- runtime and checkpoint execution.

## Evidence method

The paper was treated as the normative specification. A private line-level matrix outside Git records the detailed evidence. This public document contains only sanitized component descriptions and aggregate conclusions.

Statuses mean:

- **mapped:** the code statically indicates the same core mechanism as the paper specifies;
- **partial:** part of the mechanism is visible, but important semantics or shapes remain unresolved;
- **missing:** the scoped candidate path does not expose the specified mechanism;
- **conflicting:** there is an apparent conflict between the paper and the static code path;
- **unverified:** static dispatch is insufficient to identify the effective behavior.

## Aggregate result

The private matrix contains 27 semantic items.

| Status | Items |
|---|---:|
| Mapped | 8 |
| Partial | 7 |
| Conflicting | 7 |
| Missing | 4 |
| Unverified | 1 |

All 27 items retain the flag `runtime verification required`.

## MDP mapping

| Semantic item | Static status | Sanitized finding |
|---|---|---|
| State | Conflicting | The paper specifies queue length and maximum elapsed red-light waiting time per incoming lane. The code statically indicates raw lane counts, with inconsistent phase augmentation between the two candidates. |
| Queue aggregation | Missing | The paper specifies three queue levels using two thresholds. No corresponding transformation is visible on either candidate observation path. |
| Elapsed-time aggregation | Missing | The paper specifies a binary elapsed-time feature. No elapsed-time feature is visible on either candidate observation path. |
| Graph nodes | Mapped | The code statically indicates non-virtual intersections are indexed as graph nodes and consumed by the graph models. |
| Graph edges | Partial | The code statically indicates roads produce directed graph edges. Self-loop and exact adjacency semantics still require runtime verification. |
| Joint action | Partial | The GCAC candidate indicates one action per intersection. The GCQN candidate instead appears constrained to one action, creating an apparent conflict with the paper's node-wise action vector. |
| Phase transition | Mapped | The code statically indicates a yellow transition when the selected phase changes and continued green when it does not. Exact timing remains out of scope. |
| Reward | Conflicting | The paper specifies an equally weighted combination of queue length and elapsed waiting time. Both candidates statically indicate a negative waiting-vehicle-count reward only. |
| Terminal handling | Missing | Terminal flags are not represented in stored transitions or learning targets, and the environment path statically indicates fixed false terminal values. |

## GCQN mapping

| Semantic item | Static status | Sanitized finding |
|---|---|---|
| Action selection | Partial | Epsilon-greedy selection is present, but the candidate's scalar action assumption conflicts with the paper's per-node phase selection. |
| Replay lifecycle | Conflicting | The paper specifies episode-local collection followed by batch training. The code statically indicates a persistent buffer and updates interleaved with collection. |
| TD target | Partial | The expected reward-plus-discounted-target-maximum form is present. Node dimensions, decision-cycle indexing, and terminal behavior remain unresolved. |
| Loss | Conflicting | The paper specifies selected-action node losses with uncontrolled nodes masked. The code statically indicates a full-output mean-squared-error update without a visible uncontrolled-node mask. |
| Target updates | Mapped | Separate online and target models plus periodic hard synchronization are visible. |
| Architecture | Partial | Stacked graph-convolution layers followed by linear layers are present. Effective node and output shapes require runtime verification. |
| Parameter update | Mapped | The code statically indicates back-propagation, optimization, gradient clipping, and exploration decay. Optimizer identity is not specified within the scoped paper sections. |

## GCAC mapping

| Semantic item | Static status | Sanitized finding |
|---|---|---|
| Policy output | Mapped | The actor produces a categorical distribution over node actions. |
| Policy action | Conflicting | The paper specifies sampling from that distribution. The code statically indicates epsilon-random exploration followed otherwise by greedy argmax. |
| Actor architecture | Partial | A graph-convolution actor with a categorical action output is present, but its input-state semantics conflict with the paper state. |
| Critic architecture | Partial | A graph-convolution critic with a scalar node output is present, but input and output alignment require runtime verification. |
| Return and advantage | Conflicting | The printed paper expression has no visible discount multiplier on the next value. The code statically indicates a discounted next value. This is an apparent conflict or notation ambiguity; a paper omission remains possible. |
| Actor loss | Mapped | The code statically indicates negative log probability multiplied by detached advantage. |
| Critic loss | Mapped | The code statically indicates a squared advantage loss. |
| Optimizer behavior | Mapped | Separate actor and critic updates are visible. Optimizer identity is not specified within the scoped paper sections. |
| On-policy behavior | Conflicting | Algorithm 2 describes immediate step-wise updates, while the code statically indicates persistent replay and random mini-batch sampling. This is an apparent on-policy versus replay-based conflict. |
| Target networks | Unverified | Target actor and critic components and an alternate update path are present, but the trainer-facing target hook is empty. Static inspection cannot prove which path was used historically. |
| Terminal handling | Missing | The candidate always bootstraps and does not preserve terminal state in replay. |

## Confirmed static matches

Within the limits of source inspection, the strongest matches are:

- intersections and roads are represented as graph nodes and edges;
- changed signal phases pass through a yellow transition;
- GCQN uses epsilon-greedy selection, a target value network, and periodic synchronization;
- GCAC exposes a categorical graph actor and scalar graph critic;
- GCAC actor and critic losses have the paper's policy-gradient and squared-advantage forms;
- both agents expose explicit gradient-based parameter updates.

These are static correspondences only, not evidence that the code runs correctly or produced the paper's results.

## Apparent conflicts requiring resolution

The highest-priority apparent conflicts are:

1. paper state aggregation versus raw candidate observations;
2. the two-component paper reward versus a one-component candidate reward;
3. GCQN node-wise action and loss semantics versus scalar/full-output behavior;
4. episode-local GCQN replay versus persistent interleaved training;
5. sampled GCAC policy actions versus greedy action selection;
6. apparent GCAC discount-factor conflict or notation ambiguity;
7. on-policy A2C semantics versus replay-based random mini-batches;
8. absent terminal handling in both candidates.

## Research-integrity boundary

No finding is a successful reproduction claim. No runtime, performance, dataset, checkpoint, or stored-result conclusion has been made. Detailed evidence, including private locations, line references, and excerpts, remains outside Git.

## Next verification gate

Before any repair, establish a reviewed interpretation for each apparent conflict. The next static step is to confirm dispatch and tensor-shape expectations without importing the handovers. Runtime work should begin only after a separate environment plan and explicit approval.
