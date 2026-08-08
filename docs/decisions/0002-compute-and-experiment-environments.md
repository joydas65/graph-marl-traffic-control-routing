# Decision 0002: Separate Compute and Experiment Environments

- **Status:** Accepted
- **Date:** 8 August 2026

## Context

The primary development computer uses Apple Silicon, while the inherited GCQN and GCAC source contains evidence associated with Linux x86-64 dependencies. Development convenience, compatibility testing, and dissertation-grade experimental evidence therefore require different environment roles.

The reconstructed compatibility stack is selected from available source and package-compatibility evidence. It is not claimed to be the historical environment used for the original paper.

## Decision

Maintain four explicitly distinct compute roles.

| Role | Purpose | Evidence boundary |
|---|---|---|
| A. Development host | Editing, orchestration, analysis, and standard-library tooling | Development evidence only unless a task is architecture-independent |
| B. Compatibility-validation environment | Minimal characterization of the visible inherited source | Import, dispatch, tensor-shape, and deterministic functional evidence |
| C. Canonical dissertation environment | Baseline reproduction and controlled comparative experiments | Dissertation reproduction, training, and performance evidence |
| D. Optional exploratory compute | Bounded investigation and supplementary runs | Exploratory unless explicitly frozen, recorded, and justified |

## A. Development host

The development-host snapshot as of 8 August 2026 is:

- MacBook Pro, 16-inch, November 2024 model;
- Apple M4 Pro;
- 48 GB memory;
- Apple Silicon / arm64; and
- macOS Tahoe 26.5.2.

This host remains the primary environment for:

- source editing and Git operations;
- Codex orchestration;
- documentation and literature or research analysis;
- plotting and result analysis;
- standard-library harness development; and
- work that does not require the inherited Linux x86-64 runtime.

It is not the canonical runtime for the inherited GCQN or GCAC baseline.

The primary development host is subject to organizational endpoint controls. Local container execution is therefore not treated as an available or reproducible research dependency.

## B. Reconstructed compatibility-validation environment

The Level-1 compatibility candidate remains:

- native Linux x86-64;
- CPython 3.10.13;
- PyTorch 1.11.0+cpu;
- the approved Torch-1.11-compatible PyG dependency closure; and
- CPU-only execution.

Compatibility validation will use a dedicated native Linux x86-64 remote or cloud environment rather than local container execution or architecture emulation. No provider, machine type, operating-system image, or service has yet been validated or frozen.

This candidate is selected for installation testing only. It is not yet an installed or validated handover environment, and it is not automatically the canonical dissertation environment.

## C. Canonical dissertation experiment environment

Final baseline reproduction and comparative dissertation experiments must use controlled native Linux x86-64 infrastructure. Comparative experiments should use the same frozen environment wherever necessary for a scientifically valid comparison.

Every canonical experiment must record:

- infrastructure provider and machine type;
- native architecture;
- CPU model, where available;
- GPU model and VRAM, if used;
- vCPU count and RAM;
- operating-system or base-image identity;
- Python version and dependency lock;
- simulator versions;
- experiment configuration and seeds;
- code commit; and
- relevant dataset and network identity.

No cloud provider, machine type, GPU, or canonical image is selected by this decision.

## Performance-evidence policy

Architecture-emulated timing or performance results must not be used as final dissertation evidence. Compatibility observations such as imports, tensor shapes, dispatch, and deterministic functional behavior must remain distinct from training time, throughput, convergence speed, and comparative runtime or performance.

Canonical performance evidence requires the approved native experiment environment and its complete recorded identity.

## D. Optional exploratory compute

Google Colab and Kaggle are optional exploratory or supplementary compute. Their managed runtimes, packages, and hardware may vary, so they are not the default canonical evidence environment. A result intended as dissertation evidence must normally be rerun in the approved canonical environment unless the managed environment is explicitly frozen, recorded, and scientifically justified.

GitHub Codespaces is a possible bounded remote-development or compatibility option. It is not selected as the canonical experimental platform.

## GPU and additional-hardware policy

Do not select or purchase GPU hardware before measured baseline profiling establishes:

- training duration and whether a GPU is necessary;
- required VRAM;
- numbers of networks, seeds, and ablations;
- projected total compute; and
- cloud cost.

No additional laptop is currently justified. Dedicated hardware may be reconsidered only after workload profiling and a cloud-cost comparison. A later decision must select hardware from measured requirements rather than prescribe a model or GPU in advance.

## Research-integrity interpretation

The compatibility-selected Python, PyG, Gym, and PFRL environment is not claimed to be the historical environment used for the original paper. Successful execution in the reconstructed compatibility-validation environment would characterize the visible source under a defensible compatibility environment. It would not prove historical reproduction of the paper or establish that the reconstructed package versions match the authors' original runtime.

Historical reconstruction, present-day source compatibility, and the canonical dissertation environment remain separate questions. Claims must identify which question the evidence answers.

## Consequences

- Runtime-probe environment validation moves to disposable native Linux x86-64 remote infrastructure.
- The development host remains useful without becoming part of the inherited baseline's reproducibility claim.
- Canonical experiments require a frozen environment and complete infrastructure metadata before their results can support dissertation claims.
- Exploratory platforms may accelerate investigation but cannot silently become the evidence environment.
- GPU, provider, machine, and additional-hardware choices remain deferred until profiling supplies the required evidence.

## Review triggers

Revisit this decision after the Level-1 dependency-import and candidate probes, after baseline workload profiling, or before freezing the first canonical reproduction environment.
