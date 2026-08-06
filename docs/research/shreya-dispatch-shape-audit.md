# GCQN/GCAC Dispatch and Shape Audit

## Purpose

This document records Part 2 of `EXP-GRAPH-001`: a non-importing static trace of candidate dispatch paths and tensor-shape expectations in the private GCQN and GCAC handovers.

The findings are static evidence only. No handover module was imported, no dependency was installed, and no simulator, checkpoint, training loop, or evaluation run was executed. Every candidate-path conclusion therefore carries the requirement **runtime verification required**.

## Evidence boundary

A private line-level matrix outside Git records detailed source locations and shape derivations. This public document contains only symbolic dimensions, sanitized component roles, aggregate findings, and unresolved questions.

The audit uses:

- `N`: graph nodes or controlled intersections;
- `E`: directed graph edges;
- `F`: common per-node observation width, if node widths are homogeneous;
- `A`: action or phase count derived from the first controlled node;
- `B`: sampled replay batch size; and
- `K`: scalar GCQN input width after configured phase augmentation.

Scenario-specific values, private configurations, filenames, line references, excerpts, paths, hashes, and artifacts are intentionally excluded.

Findings use the labels **statically known**, **statically inferred**, **candidate path**, and **apparent mismatch** as appropriate. Any unresolved behavioural conclusion is marked **runtime verification required**.

## Shared candidate dispatch

The shared framework statically indicates this top-level sequence:

`runner -> configuration merge -> registry -> task -> trainer -> world/environment -> selected agent -> replay/batch -> model/loss/update -> evaluation`

The runner's import order makes one configuration builder the candidate definition selected by the visible dispatch while leaving an older builder shadowed. The default agent selection does not correspond to a registered graph model, so a graph candidate requires an explicit selection. No preserved command establishes the historical selection, simulator, network, or configuration.

## GCQN competing candidate paths

The handover exposes two separately selectable graph-Q candidates. Neither is established as the historical or authoritative GCQN implementation.

### Candidate S: scalar or single-intersection graph-Q

Candidate S is statically inferred to create one trainer-level agent with one sub-agent. It observes the first controlled intersection, returns one action and one reward, and stores scalar-action transitions.

| Boundary | Statically inferred shape |
|---|---|
| Reset observation | outer `[1]`, inner `[1, F]` |
| Phase | trainer `[1, 1]`; agent `[1]` |
| Action | scalar; trainer/environment `[1]` |
| Reward and done | reward `[1]`; done `[1]` |
| Replay state | `[1, F]` with scalar action and reward |
| Sampled features | `[B, K]` |
| Stored graph edges | `[2, E]` for an `N`-node network |
| Q output | inference `[1, A]`; training `[B, A]` |
| TD target | `[B]` |
| Loss inputs | prediction and target `[B, A]` |

The candidate pairs one inference row, or `B` replay rows, with an edge index describing `N` network nodes. This is an **apparent mismatch** whenever the selected graph has more than the compatible single-node case. Static inspection cannot determine whether a particular historical configuration avoided, exposed, or masked the mismatch; runtime verification is required.

The alternative simulator path also does not statically expose the graph-edge attribute consumed by Candidate S.

### Candidate N: full-network node-wise graph-Q

Candidate N is separately selectable and statically inferred to create one trainer-level object controlling `N` nodes. It produces one observation, action, and reward per node.

| Boundary | Statically inferred shape |
|---|---|
| Reset observation | `[N, F]` |
| Phase | `[N]` |
| Action | `[N]` |
| Reward and done | reward `[N]`; done `[N]` |
| Replay state | `[N, F]` with action/reward `[N]` |
| Sampled node features | `[B N, F]` |
| Constructed batched edges | `[2, B E]` |
| Q output | inference `[N, A]`; training `[B N, A]` |
| TD target | `[B N]` |
| Loss inputs | prediction and target `[B N, A]` |

Batch construction statically produces offset edges for `B` graphs, but training passes only the concatenated node features to a model retaining the original `[2, E]` edge index. The `[2, B E]` batched edge index is not used on the candidate training path. This is an apparent graph-batch mismatch and requires runtime verification.

Candidate N is structurally closer to the paper's node-wise graph-Q description than Candidate S, but structural proximity is not provenance. The audit does not designate either candidate as authoritative.

## GCAC candidate path

The GCAC candidate is statically inferred to create one trainer-level actor-critic object controlling `N` nodes. The graph-enabled configuration constructs an `N`-node edge index, and inference returns one categorical action decision per node.

| Boundary | Statically inferred shape |
|---|---|
| Reset observation | outer `[1]`, inner `[N, F]` |
| Phase | trainer `[1, N]`; not consumed by the candidate model |
| Action | agent `[N]`; trainer `[1, N]`; environment `[N]` |
| Reward and done | reward `[N]`; done `[N]` |
| Replay state | `[N, F]` with action/reward `[N]` |
| Sampled node features | `[B N, F]` |
| Constructed batched edges | `[2, B E]` |
| Actor output | inference `[N, A]`; training `[B N, A]` |
| Critic output | inference `[N, 1]`; training `[B N, 1]` |
| Return and advantage | `[B N]` |
| Actor and critic losses | scalar reductions over `[B N]` terms |

The batch builder statically creates offset graph edges, but the candidate training method selected by the standard trainer extracts only the concatenated features. The actor and critic then use their stored single-graph `[2, E]` edge index. The constructed `[2, B E]` edge index is discarded on this candidate path.

The return vector contains `B N` positions, but the visible update loop assigns only a prefix of length `B`. When `N > 1`, the remaining entries retain their cloned current values, which statically indicates zero apparent advantage for those entries. This is an apparent partial return-update mismatch; runtime verification is required.

## Cross-path shape findings

| Finding | Candidate S | Candidate N | GCAC |
|---|---|---|---|
| One trainer-level agent object | Statically known | Statically known | Statically known |
| Node-wise environment action | No; `[1]` | Yes; `[N]` | Yes; `[N]` |
| Node-wise replay state | No; `[1, F]` | Yes; `[N, F]` | Yes; `[N, F]` |
| Offset batched edges constructed | No graph batch | Yes | Yes |
| Constructed batched edges used | No | No | No |
| Terminal stored in replay | No | No | No |
| Terminal target mask | No | No | No |
| Target network used by standard trainer-connected update | Yes | Yes | No |

All candidates derive model input width and action count from a leading controlled node. Homogeneous `F` and `A` across all nodes are therefore assumptions, not statically verified invariants.

## Apparent mismatches

The highest-priority static findings are:

1. Candidate S combines scalar observation/action semantics with a potentially full-network graph.
2. Candidate S treats replay rows as graph nodes rather than representing `B` independent `N`-node graphs.
3. Candidate N constructs batched graph edges but trains with the original unbatched edge index.
4. GCAC likewise discards its constructed batched edges during the standard candidate training path.
5. GCAC updates only a `B`-element prefix of a `B N` return vector.
6. The environment's declared multi-node action-space structure does not match the node-wise vector supplied by the trainer.
7. Node feature width and action count assume homogeneous intersections without a visible validation gate.
8. No candidate preserves terminal state or applies terminal-aware bootstrapping.

These are static audit questions, not proof of runtime failure or evidence about which implementation produced the paper's results.

## Terminal propagation

The common terminal path is statically inferred as:

`environment all-false done vector -> trainer-selected done value -> remember argument -> omitted replay field -> unconditional bootstrap`

For a single trainer-level multi-node agent, the trainer passes only one element of the `N`-element done vector. Every scoped candidate then omits that value from replay. The sampled batches contain no terminal mask, and their targets or returns always bootstrap.

## Target-network dispatch

- **Candidate S:** a target Q-network is constructed, initially synchronized, used for TD targets, and periodically hard-updated by the standard trainer.
- **Candidate N:** the same standard trainer-connected target-Q pattern is statically visible for the full-network graph-Q update.
- **GCAC:** target actor and critic networks are constructed and initially synchronized. The standard trainer calls an empty target-update hook, and its selected actor-critic update uses current networks only. Target use and subsequent synchronization appear confined to a competing alternate training method with no standard caller.

The GCAC target path is therefore classified as unverified rather than definitively unused.

## Evaluation and checkpoint dispatch

Evaluation reuses the respective candidate action paths without replay updates:

- Candidate S returns one action;
- Candidate N returns `N` node actions; and
- GCAC returns `N` node actions from the current actor.

The standard task-level test call does not explicitly select checkpoint loading, while the lower-level evaluation helper loads only under a different flag value. A test-only invocation may therefore evaluate newly constructed parameters unless another preceding path retained trained parameters in memory. Candidate S's trainer also contains an evaluation call after training, while the other handover's trainer relies on task-level testing.

This is an evaluation and checkpoint-loading ambiguity, not a successful-load or failed-load claim.

## Research-integrity decision

- Treat Candidate S and Candidate N as competing selectable GCQN candidates.
- Do not call either candidate historical, authoritative, reproduced, or correct.
- Treat the GCAC dispatch as a candidate path with unresolved graph batching, return coverage, terminal handling, target dispatch, and evaluation loading.
- Keep line-level evidence and all private implementation identifiers outside Git.
- Do not repair or execute the handovers until mentors confirm the intended source/configuration lineage and a separate runtime-verification plan is approved.

## Next verification gate

Prepare a minimal, non-training runtime-probe plan that tests dispatch and tensor invariants without silently repairing the candidates. The plan must define expected shapes, supported environment versions, synthetic or minimal scenarios, failure criteria, and evidence capture before any handover import or execution is authorized.
