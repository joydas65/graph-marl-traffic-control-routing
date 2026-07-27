# Decision 0001: Maintain One Longitudinal Research Repository

- **Status:** Accepted
- **Date:** 27 July 2026

## Context

The project begins from Shreya Salmalge's public single-intersection DQN repository but is intended to progress through baseline reproduction, graph multi-agent control, disruptions, dynamic routing, and a dissertation contribution. Two structures were considered:

1. retain one fork only as a baseline and create a separate dissertation repository; or
2. use one fork as the complete, traceable research history.

The student needs to demonstrate sustained research effort over approximately ten months while keeping inherited and original contributions distinguishable.

## Decision

Use `joydas65/graph-marl-traffic-control-routing` as the single longitudinal repository.

Preserve the exact inherited state with annotated tag `baseline-shreya-dqn-original` at commit `dab14cd6deac66a9116bf85fd40003b6ca2ec451`. All new work follows that tag.

Keep these remotes:

- `origin`: Joy's fork
- `upstream`: Shreya's original repository

Develop milestone changes on focused branches and merge through reviewable pull requests. Use additional milestone tags only when an acceptance gate is satisfied.

## Why

- One history makes the research progression easy to review.
- The upstream commit and tag distinguish inherited code from subsequent work.
- Baseline repair, negative findings, experiments, and methodological changes remain connected.
- Documentation and code evolve together.
- The final repository can support dissertation examination and future publication work.

## Consequences

- The repository must not obscure upstream provenance.
- Root structure may need careful migration as the prototype becomes a research platform.
- Baseline repairs and new algorithms must be separated in commits and experiment records.
- The repository's public nature requires strict exclusion of administrative, personal, copyrighted, credential, and company-confidential material.
- A high commit count is not an objective; each milestone must have reproducible evidence.

## Planned milestone markers

- `baseline-shreya-dqn-original`: untouched inherited code
- `dqn-reproduction-v1`: deterministic Level-0 reproduction
- `gcqn-gcac-reproduction-v1`: accepted graph-paper baseline
- `disruption-environment-v1`: frozen incident benchmark
- `two-timescale-method-v1`: first complete proposed method
- `dissertation-evaluation-v1`: frozen final evaluation code and configs

Names after the preservation tag remain provisional until the relevant gate is reached.
