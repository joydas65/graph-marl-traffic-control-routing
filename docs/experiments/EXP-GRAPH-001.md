# EXP-GRAPH-001: Paper-to-Code Semantic Audit

## Status

Parts 1 and 2 are complete as non-executing static audits. Runtime verification has not started.

## Question

Do the private GCQN and GCAC handovers statically implement the MDP and learning procedures specified in Sections 2.1-3.3 and Algorithms 1-2 of the Salmalge-Bhatnagar paper?

## Scope completed

### Part 1: paper-to-code semantics

- state and state aggregation;
- graph nodes and edges;
- action and phase handling;
- reward, replay, and terminal handling;
- GCQN action selection, target, loss, architecture, and target updates;
- GCAC policy, actor, critic, advantage, losses, optimizer behavior, and replay semantics.

### Part 2: dispatch and symbolic shapes

- runner, configuration, registry, task, trainer, environment, agent, replay, model, update, and evaluation dispatch;
- symbolic reset, phase, action, reward, done, replay, batch, graph, output, target/return, and loss shapes using `N`, `E`, `F`, `A`, `B`, and `K`;
- competing scalar and full-network node-wise GCQN candidate paths;
- GCAC graph-batch, return-update, terminal, target-network, and checkpoint-dispatch questions.

Section 4, experiment figures and tables, datasets, stored results, installation, training, and checkpoint execution were explicitly excluded.

## Method

1. Treated the complete paper as the normative specification.
2. Inspected both external handovers read-only.
3. Traced candidate observation, graph, action, reward, replay, trainer, network, loss, and update paths.
4. Recorded detailed line-level semantic and dispatch/shape evidence in private matrices outside Git.
5. Reduced that evidence to aggregate, public-safe findings.

No handover module was imported or executed. No dependency was installed.

## Part 2 static dispatch findings

The GCQN handover contains two competing selectable graph-Q candidates:

- a scalar or single-intersection candidate that combines `[1, K]` inference input with an `N`-node edge index; and
- a full-network node-wise candidate with `[N, F]` inference input and `[N, A]` Q output.

Neither candidate is established as the historical or authoritative GCQN implementation. The full-network candidate constructs `[2, B E]` batched edges but statically passes `[B N, F]` features to a model retaining the unbatched `[2, E]` edge index.

The GCAC candidate similarly constructs batched edges and then discards them on the training path selected by the standard trainer. Its return vector has `B N` entries, while the visible assignment loop updates only a prefix of length `B`. These are apparent mismatches, and runtime verification is required.

All scoped candidates omit terminal state from replay and apply no terminal target mask. GCQN target Q-networks are statically connected on both selectable graph-Q paths. GCAC target actor/critic networks are initialized, but standard target updates are empty and target use appears confined to an alternate method without a standard caller.

The public symbolic audit is recorded in [`../research/shreya-dispatch-shape-audit.md`](../research/shreya-dispatch-shape-audit.md).

## Aggregate evidence

| Status | Count |
|---|---:|
| Mapped | 8 |
| Partial | 7 |
| Conflicting | 7 |
| Missing | 4 |
| Unverified | 1 |

All 27 semantic items require runtime verification.

## Static interpretation

The code statically indicates genuine graph-Q and graph actor-critic components, including graph construction, graph-convolution layers, a target Q network, a categorical actor, a scalar critic, and recognizable TD and actor-critic loss forms.

However, the audit found apparent conflicts in the state, reward, GCQN action/loss, replay lifecycle, GCAC action selection, GCAC discount-factor notation, and on-policy semantics. Terminal handling is not visible on either candidate learning path.

These findings establish audit questions. They do not prove defects, effective runtime behavior, or divergence from the implementation used to produce the paper.

## Evidence classification

- **Paper evidence:** complete Sections 2.1-3.3 and Algorithms 1-2.
- **Static implementation evidence:** read-only inspection of the two private handovers.
- **Runtime evidence:** none.
- **Reproduction evidence:** none.
- **Performance evidence:** none.

## Research-integrity constraints

- No private handover path, filename, line number, excerpt, hash, timestamp, raw configuration, dataset detail, log, or checkpoint identifier is stored in Git.
- No algorithm was repaired or changed.
- No paper result is attributed to the handovers.
- The inherited DQN reproduction track remains separate.

## Decision

Do not repair or run either handover yet. Confirm the intended source/configuration lineage and review the dispatch/shape questions, especially the competing GCQN candidates, discarded batched edges, GCAC return coverage, terminal propagation, target dispatch, and evaluation loading.

## Next gate

Prepare a separately approved, minimal, non-training runtime-probe plan for dispatch and tensor invariants. Environment installation and handover execution remain outside this experiment stage.
