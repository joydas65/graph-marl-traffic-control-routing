# Inherited DQN Repository Audit

## Audit identity

- **Upstream:** <https://github.com/Shreya-Salmalge/Traffic-Light-Control-using-DQN>
- **Audited commit:** `dab14cd6deac66a9116bf85fd40003b6ca2ec451`
- **Audit date:** 26 July 2026
- **Coverage:** all 15 tracked files
- **Preservation tag in this fork:** `baseline-shreya-dqn-original`

## Verdict

The inherited repository is a single-agent, single-intersection DQN/SUMO prototype. It is useful for learning and smoke-testing the SUMO-TraCI lifecycle, route generation, phase transitions, queue/wait measurements, replay memory, and elementary DQN training.

It is not the multi-intersection GCQN/GCAC implementation described in the 2025 Salmalge-Bhatnagar paper. It contains no graph convolution, multi-agent coordination, routing policy, disruption model, CTDE, or two-timescale learning mechanism.

It also cannot currently support trustworthy dissertation evidence. Several implementation inconsistencies prevent valid end-to-end training and testing.

## Implemented system

| Item | Inherited implementation |
|---|---|
| Simulator | SUMO controlled through TraCI |
| Network | One four-arm signalised junction, ID `TL` |
| Approaches | North, south, east, west; four incoming lanes each |
| Actions | Four green-phase choices |
| Timing | 10 seconds green; 4 seconds yellow when action changes |
| Horizon | 5,400 simulation steps |
| Demand | 1,000 vehicles; Weibull-shaped departures; 12 OD routes |
| Agent | One DQN controlling the junction |
| Training state | 32 values: 24 distance occupancy flags plus 8 waiting flags |
| Training reward | Reduction in total waiting plus reduction in total queue |
| Replay | Capacity 50,000; minimum 600; batch 100 |
| Discount | 0.75 |
| Exploration | Linear epsilon decay across 100 episodes |
| Configured optimisation | Learning rate 0.001; 800 replay updates per episode |

## File inventory

| File | Purpose and finding |
|---|---|
| `README.md` | Originally only a title; no execution or research documentation. |
| `TLCS/training_main.py` | Training orchestration; assumes execution from `TLCS`. |
| `TLCS/training_simulation.py` | TraCI loop, state, action, reward, replay, statistics. |
| `TLCS/modelP.py` | PyTorch network with critical layer-registration and device defects. |
| `TLCS/memory.py` | Uniform replay deque; Python RNG not seeded. |
| `TLCS/generator.py` | Weibull demand and 12 route definitions; only NumPy seeded. |
| `TLCS/training_settings.ini` | Uses 32 states, 4 actions, four hidden layers of width 256. |
| `TLCS/testing_main.py` | Imports a missing `model.py` and `TestModel`. |
| `TLCS/testing_simulation.py` | Uses an absent `predict_one` API and an incompatible state. |
| `TLCS/testing_settings.ini` | Configures 80 states, contradicting training. |
| `TLCS/utils.py` | Settings, SUMO command, and output-directory helpers. |
| `TLCS/visualization.py` | Basic plots and raw text-series export. |
| `TLCS/intersection/environment.net.xml` | Single-junction SUMO network and phases. |
| `TLCS/intersection/episode_routes.rou.xml` | Generated sample containing 1,000 vehicles. |
| `TLCS/intersection/sumo_config.sumocfg` | Loads network and routes; disables teleportation. |

## MDP interpretation

### Observation

Eight lane groups each contribute three coarse distance-occupancy indicators, producing 24 features. Eight additional flags indicate whether corresponding vehicles have waited for at least 13 seconds, producing 32 training features.

The encoding omits queue magnitude, exact waiting, speed, density, current phase, phase age, downstream occupancy, neighbouring junctions, graph structure, and incident/capacity state. It may remain as an intentionally weak inherited comparator but is insufficient for the final dissertation method.

### Action

Four actions represent legal green patterns: north/south through-right, north/south left, east/west through-right, and east/west left. A four-second yellow phase is inserted when the action changes before the new ten-second green. This transition pattern is reusable after safety constraints and phase validity are tested explicitly.

### Reward

Training calculates:

`old_total_wait - current_total_wait + old_total_queue - current_total_queue`

This is a change in congestion cost, not the same reward as the 2025 graph paper. It can be influenced by vehicles entering or leaving the network. The repaired baseline must retain it initially for faithful reproduction, then compare alternative reward definitions through an explicit experiment rather than silently changing it.

### Learning

The online network both predicts and supplies bootstrap targets. There is no target network, Double DQN, terminal flag, gradient clipping, or checkpoint metadata. Eight hundred replay updates are configured after each episode, creating substantial cost without common DQN stabilisation mechanisms.

## Critical defects

1. **Hidden layers are not registered.** `modelP.py` stores `nn.Linear` layers in a plain Python list. PyTorch therefore omits them from `parameters()`, optimiser updates, `state_dict()`, and device movement.
2. **Testing import is missing.** `testing_main.py` imports `TestModel` from `model.py`, but no such file exists.
3. **Testing calls an absent API.** `testing_simulation.py` expects `predict_one`, which the PyTorch model does not provide.
4. **Training and testing observations conflict.** Training uses 32 features; testing uses a different 80-feature distance encoder.
5. **Device handling is inconsistent.** The model may move to CUDA while tensors remain on CPU.

## High-priority reproducibility gaps

- No dependency or environment specification.
- No target network or terminal-aware transition.
- Python `random` and PyTorch are not seeded.
- No reference checkpoint, metrics, raw result, seed set, or expected baseline range.
- Training and testing reward accounting differs.
- Relative paths depend on launching from `TLCS`.
- No tests, CI, configuration validation, or deterministic smoke test.
- No classical traffic-control comparator.
- No declared licence.

## Reusable reference components

- SUMO process lifecycle and TraCI stepping.
- Four-arm network for rapid smoke tests.
- Episode demand-generation concept and OD routes.
- Action-to-green/yellow phase mapping.
- Queue and accumulated-wait extraction.
- Replay-buffer concept.
- Configuration and plotting skeleton.
- Original state and reward as inherited comparison points.

These components require tests and interfaces before use in the new architecture.

## Required repair sequence

1. Declare supported versions and create a reproducible environment.
2. Add a root-level command and path-independent configuration loading.
3. Register all network modules and make tensor/device handling consistent.
4. Establish one observation, reward, and model interface for both training and testing.
5. Represent episode termination in replay.
6. Seed every stochastic component.
7. Add unit tests for state dimensions, action transitions, parameter registration, checkpoint round trips, and replay targets.
8. Add a deterministic one-episode integration test using SUMO without GUI.
9. Record runtime and compare against fixed-time or round-robin control.
10. Run multiple seeds and define the expected result range before calling reproduction complete.

## Reproduction acceptance criteria

The Level-0 baseline is reproduced only when:

- a clean environment can be installed from repository instructions;
- training and evaluation run from the repository root;
- tests prove every intended layer is registered and updated;
- a saved checkpoint reloads and reproduces evaluation behaviour;
- the same seeds reproduce demand, action selection, replay sampling, and reported metrics within documented tolerance;
- at least one non-learning comparator runs on identical scenarios;
- per-seed raw data and aggregate metrics are retained; and
- known deviations from the inherited code are documented.

## Dissertation migration

After Level 0, implement a separate tested environment/agent architecture within this same repository. Progress through GCQN/GCAC reproduction, graph environment construction, disruption modelling, two-timescale routing, coordination ablations, and unseen-scenario evaluation. Do not incrementally stretch the untested prototype until its assumptions become invisible.

## Mentor confirmations required

- Whether this repository produced any reported experimental result or was an earlier prototype.
- The location of the authoritative 2025 codebase; `traffic-signal-control/RL_signals` was inspected and contains no GCQN/GCAC implementation.
- Original Python, SUMO, framework, and dependency versions.
- Intended observation dimension: 32 or 80.
- Missing model/checkpoint/testing files and expected baseline numbers.
- Reuse, attribution, and licence expectations.
