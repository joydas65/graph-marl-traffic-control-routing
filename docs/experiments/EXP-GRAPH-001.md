# EXP-GRAPH-001: Paper-to-Code Semantic Audit

## Status

Part 1 complete as a non-executing static audit. Runtime verification has not started.

## Question

Do the private GCQN and GCAC handovers statically implement the MDP and learning procedures specified in Sections 2.1-3.3 and Algorithms 1-2 of the Salmalge-Bhatnagar paper?

## Scope completed

- state and state aggregation;
- graph nodes and edges;
- action and phase handling;
- reward, replay, and terminal handling;
- GCQN action selection, target, loss, architecture, and target updates;
- GCAC policy, actor, critic, advantage, losses, optimizer behavior, and replay semantics.

Section 4, experiment figures and tables, datasets, stored results, installation, training, and checkpoint execution were explicitly excluded.

## Method

1. Treated the complete paper as the normative specification.
2. Inspected both external handovers read-only.
3. Traced candidate observation, graph, action, reward, replay, trainer, network, loss, and update paths.
4. Recorded detailed line-level evidence in a private matrix outside Git.
5. Reduced that evidence to aggregate, public-safe findings.

No handover module was imported or executed. No dependency was installed.

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

Do not repair or run either handover yet. First review the apparent conflicts and confirm the intended historical execution path, especially GCQN node-wise control and GCAC replay-based behavior.

## Next gate

Complete a non-importing dispatch and tensor-shape audit for the candidate paths. Environment installation and runtime verification require a separate approved experiment plan.
