# Repository Guidance for Codex and Other Contributors

## Purpose

This repository is the longitudinal research record for Joy Das's M.Tech dissertation. Optimise for scientific correctness, reproducibility, provenance, and reviewability rather than rapid feature accumulation.

Before material work, read:

1. `docs/project-context.md`
2. `docs/research/roadmap.md`
3. `docs/research/baseline-audit.md`
4. `docs/progress/monthly-effort-log.md`

## Immutable provenance

- `baseline-shreya-dqn-original` identifies the untouched inherited baseline at commit `dab14cd6deac66a9116bf85fd40003b6ca2ec451`.
- Never move, recreate, or delete that tag.
- Never rewrite published history or force-push shared branches.
- Keep `origin` pointed at Joy's fork and `upstream` pointed at Shreya's repository.
- Preserve attribution when code is reorganised or rewritten.
- The upstream licence is unresolved; do not claim permission or add a repository-wide licence without explicit confirmation.

## Research scope

The intended contribution combines:

- graph-based multi-agent traffic-signal control;
- disruption-aware node and edge features;
- slower dynamic routing decisions;
- frequent signal decisions;
- an explicit coordination/learning mechanism for the two timescales; and
- evaluation under unseen demand and disruption conditions.

Raw camera processing, production deployment, proprietary Walmart data, and a real-city deployment are outside the minimum dissertation scope.

## Engineering requirements

- Use Python, SUMO/TraCI, PyTorch, and an explicitly selected graph-learning library.
- Keep simulator interaction separate from agent, observation, reward, metrics, and experiment orchestration code.
- Centralise configuration; do not hide experiment settings in source files.
- Seed Python, NumPy, PyTorch, the simulator demand generator, and any graph sampler.
- Treat CPU/GPU selection and tensor placement consistently.
- Add tests for every repaired defect and every environment invariant.
- Prefer small deterministic smoke tests before expensive training.
- Do not silently change the MDP, demand model, signal timing, or evaluation metrics.

## Experiment evidence

Every experiment record must contain:

- an explicit hypothesis or question;
- the Git commit and configuration file;
- seed set and scenario identifiers;
- dependency and SUMO versions;
- hardware and runtime;
- raw per-run outputs;
- aggregate metrics and uncertainty;
- failures, exclusions, and unfinished trips;
- interpretation and the resulting decision.

Results without this metadata are exploratory only and must not be used as dissertation evidence.

## Git workflow

- Keep `main` reviewable and runnable at documented milestones.
- Use short-lived branches such as `baseline/dqn-reproduction`, `baseline/gcqn-reproduction`, `feature/disruption-environment`, and `feature/two-timescale-routing`.
- Use focused commits that explain why a change is made.
- Use pull requests for milestone changes, even when working alone, so the research reasoning remains reviewable.
- Do not commit generated checkpoints, large raw outputs, copyrighted papers, signatures, emails, student identifiers, credentials, or company-confidential material.
- Do not commit or push unless the user explicitly requests it.

## Documentation obligations

- Update `docs/progress/monthly-effort-log.md` when a meaningful activity is completed.
- Record architectural or methodological choices under `docs/decisions/`.
- Update the baseline audit when reproduction evidence changes its conclusions.
- Distinguish verified facts, mentor guidance, working decisions, assumptions, and proposed ideas.
- Never overstate a prototype, partial result, or directional improvement as a scientific conclusion.

## Verification before handoff

Run the narrowest relevant tests and static checks, inspect the diff, and report what was verified and what remains unverified. Expensive experiments require a saved configuration and explicit approval before launch.
