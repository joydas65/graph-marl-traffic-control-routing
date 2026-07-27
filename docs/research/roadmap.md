# Gated Research Roadmap

## Objective

Develop and evaluate a disruption-aware graph multi-agent reinforcement-learning method that coordinates frequent traffic-signal decisions with slower dynamic-routing decisions. The work should be defensible as research, reproducible as software, and traceable from inherited baselines.

## Phase 0: provenance and research foundation

**Status:** substantially complete in July 2026.

### Deliverables

- Preserve the untouched inherited commit.
- Audit every inherited file and identify reproduction blockers.
- Establish one public-safe research repository and documentation system.
- Verify the SUMO/TraCI toolchain independently.
- Confirm the foundational literature and mentor roles.

### Gate

The inherited state, known defects, current scope, and next reproduction task are reviewable without relying on private chat history.

## Phase 1: deterministic DQN baseline

**Provisional period:** August-September 2026.

### Research purpose

Establish a trustworthy experimental pipeline and determine what the inherited DQN actually learns when implementation defects are repaired.

### Deliverables

- Reproducible environment and dependency specification.
- Correct registered model, device handling, terminal-aware replay, checkpoint loading, and consistent evaluation.
- Complete seed control and automated unit/integration tests.
- Fixed-time or round-robin comparator.
- Multi-seed baseline metrics and runtime profile.
- Deviation log distinguishing faithful repairs from algorithmic improvements.

### Gate

Another machine can run the experiment, reload its checkpoint, and reproduce documented metrics within tolerance.

## Phase 2: GCQN/GCAC paper baseline

**Provisional period:** October-November 2026.

### Research purpose

Re-establish the direct 2025 baseline on a multi-intersection graph and understand its sensitivity before proposing extensions.

### Deliverables

- Mentor-confirmed authoritative source and experiment configuration.
- Reconstructed node/edge features, actions, rewards, timing, and training protocol.
- GCQN, GCAC, individual-DQN, central-DQN where tractable, and round-robin/max-pressure comparisons.
- Multi-seed directional reproduction with explicit deviations from the paper.
- Profiling of scalability and retraining behaviour.

### Gate

Mentors agree that the inherited graph baseline is sufficiently faithful for extension and that discrepancies are understood.

## Phase 3: disruption-aware graph environment

**Provisional period:** December 2026-January 2027.

### Research questions

- Which incident features allow transfer to unseen disruption locations?
- How much does explicit capacity/availability information improve recovery?
- Can topology- or mask-aware graph processing reduce retraining needs?

### Deliverables

- Reproducible accident, closure, capacity-reduction, and demand-surge generator.
- Training/validation/test split across locations, severities, and demand patterns.
- Safety-consistent action masks and network reachability checks.
- Disruption-aware graph signal controller.
- Recovery, tail-delay, spillback, and fairness metrics.

### Gate

The graph controller demonstrates a reproducible and statistically supported benefit or produces a clear negative result that informs the final method.

## Phase 4: two-timescale signal and routing coordination

**Provisional period:** February-March 2027.

### Central research requirement

Specify an algorithmic coupling, not simply two independent policies. Candidates may include centralised critics, hierarchical objectives, shared graph encoders, counterfactual credit assignment, or constrained macro-action updates. The selection must follow evidence and mentor review.

### Deliverables

- Formal state, action, reward, transition, and timing definition for both layers.
- Routing action abstraction that remains computationally manageable.
- Explicit asynchronous learning update.
- Coordination ablations:
  - signals only;
  - routing only;
  - independent joint control;
  - graph joint control without timescale separation;
  - proposed two-timescale coordination.
- Stability, runtime, generalisation, recovery, and fairness results.

### Gate

The proposed coupling has a measurable, interpretable advantage or the fallback scope is activated with documented mentor approval.

## Phase 5: final evaluation and research communication

**Provisional period:** April-May/June 2027.

### Deliverables

- Frozen evaluation protocol and untouched test scenarios.
- Multiple seeds, uncertainty intervals, and statistical comparisons.
- Sensitivity analysis and failure-case study.
- Complete ablation table.
- Reproducibility package with commands, configs, manifests, and raw result indices.
- Dissertation, evaluation presentation, and publication-oriented manuscript outline.

### Gate

Every headline claim is linked to reproducible evidence and a controlled comparison.

## Evidence hierarchy

1. **Smoke evidence:** code executes and invariants hold.
2. **Reproduction evidence:** known baseline behaviour is recreated.
3. **Ablation evidence:** a component's causal contribution is isolated.
4. **Generalisation evidence:** performance holds on unseen conditions.
5. **Research evidence:** the proposed mechanism is competitive, interpretable, reproducible, and bounded by documented limitations.

Only Levels 3-5 should support the central dissertation claim.

## Mentor communication rhythm

- Technical co-mentor: focused implementation/reproduction syncs as needed, ideally weekly or fortnightly during active experiments.
- Primary company mentor: progress, feasibility, evaluation, and formal review alignment.
- Faculty mentor: concise milestone updates centred on research question, evidence, interpretation, and decisions requiring academic guidance.
- Monthly: update the effort log, roadmap status, risks, and next gate.

## Scope protection

Do not add temporal networks, continuous control, real-world data, advanced routing abstractions, or additional algorithms merely to increase visible work. Add a component only when it answers a defined research question and has an evaluation plan.
