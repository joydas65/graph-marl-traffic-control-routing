# Monthly Dissertation Effort Log

## Project period

August 2026 to May/June 2027. This log begins with pre-project preparation in July 2026.

## July 2026: pre-project preparation

### Research and mentoring

- Prepared and refined the dissertation proposal.
- Obtained mentor agreement on the proposed direction.
- Analysed the complete 2025 Salmalge-Bhatnagar GCQN/GCAC paper and mapped its stated future work to the dissertation.
- Analysed the 2011 Prashanth-Bhatnagar traffic-signal-control paper and recorded the research lineage.
- Identified the 2014 multi-agent traffic-signal-control work as an additional distributed-control reference.
- Held the initial technical discussion with Shreya.
- Agreed to study DQN, actor-critic, GCN, SUMO, and TraCI before reproducing the inherited model.
- Recorded the warning that hyperparameter tuning and simulation runtime will require substantial experiment time.
- Established monthly progress logging and regular mentor syncs as project practices.

### Technical environment: 21 July 2026

- Installed XQuartz and restarted macOS for SUMO graphical support.
- Diagnosed the original `zsh: command not found: sumo` issue and confirmed SUMO was not yet installed.
- Investigated the `dlr-ts/sumo` Homebrew formula failure caused by incompatibility with the installed Homebrew version.
- Downloaded and inspected the official Eclipse SUMO 1.27.1 Apple Silicon package before installation.
- Installed the SUMO framework and graphical applications.
- Configured stable `SUMO_HOME`, `PATH`, and `PYTHONPATH` values.
- Verified `sumo`, `sumo-gui`, `netedit`, TraCI, and `sumolib`.
- Diagnosed the absence of the documentation/tutorial tree in the macOS package.
- Obtained the matching quickstart files separately without changing the valid framework installation.
- Completed the official 900-second CLI quickstart with 1,440 inserted vehicles.
- Completed the GUI quickstart and confirmed normal final-step termination.
- Investigated XQuartz `BadValue`, `xp_destroy_surface`, and `GLXBadContext` messages and classified them as display-context cleanup warnings rather than simulation failures.
- **Outcome:** SUMO/TraCI development environment verified for baseline reproduction.

### Repository analysis: 26 July 2026

- Received and cloned Shreya's `Traffic-Light-Control-using-DQN` repository.
- Pinned the audit to commit `dab14cd6deac66a9116bf85fd40003b6ca2ec451`.
- Inspected all 15 tracked source, configuration, network, route, and documentation files.
- Classified it as a single-agent, single-intersection DQN/SUMO prototype rather than the 2025 GCQN/GCAC implementation.
- Documented the MDP, network, demand generation, action timing, training loop, replay, and configured hyperparameters.
- Identified critical reproduction blockers, including unregistered PyTorch hidden layers, broken testing imports/API, 32-versus-80 feature mismatch, incomplete device handling, and incomplete seeding.
- Mapped reusable simulator components and required dissertation redesigns.

### Repository establishment: 27 July 2026

- Forked Shreya's repository to <https://github.com/joydas65/graph-marl-traffic-control-routing>.
- Selected a single-repository strategy so the progression from inherited baseline to dissertation contribution remains traceable.
- Cloned the fork into the dissertation workspace.
- Verified `origin` points to Joy's fork.
- Added `upstream` pointing to Shreya's original repository.
- Created local annotated tag `baseline-shreya-dqn-original` at commit `dab14cd` to preserve the untouched baseline. Remote tag publication is pending.
- Added a public-safe documentation system containing provenance, project context, mentor guidance, foundational literature, baseline audit, roadmap, research decision record, and this monthly log.
- Added `AGENTS.md` so future Codex work follows the same scientific, provenance, experiment, and privacy requirements.

### Joint mentor meeting and RL foundations: 27-28 July 2026

- Met jointly with Arghya Roy Chaudhuri and Shreya Salmalge.
- Shreya explained the intuition for representing the road network as a graph and using neighbouring congestion in signal decisions.
- Arghya's technical questions identified the need to strengthen first-principles RL and graph understanding.
- Began Sutton and Barto and reached Chapter 1, Section 1.5 by 28 July.
- Established chapter evidence requirements: explain-back notes, equations, traffic-control mapping, questions, and related code/experiments.
- Formalised the complete MDP described in the Salmalge-Bhatnagar paper.
- Reworked the MDP note using rendered LaTeX and rewrote the Chapter 1, mentor-question, and joint-meeting notes in a more natural first-person research voice.
- Corrected cross-platform equation rendering by adopting GitHub fenced-math blocks and adding a standalone, Overleaf-ready LaTeX source.
- Created a question bank; the exact wording of Arghya's questions remains to be reconstructed and will not be invented.
- Inspected the paper-linked `traffic-signal-control/RL_signals` repository and established that it is a general resource catalogue rather than the GCQN/GCAC implementation.
- Prepared the first weekly update and the `EXP-DQN-000` inherited-baseline preflight.
- Started the `baseline/dqn-reproduction` milestone branch for faithful execution, diagnosis, repair, and comparison of Shreya's public DQN prototype.

### Decisions

- Maintain one longitudinal research repository rather than a disposable baseline fork plus disconnected dissertation repository.
- Preserve the inherited state with a tag and record every subsequent methodological milestone through focused branches, commits, pull requests, and milestone tags.
- Treat the inherited DQN as Level 0 only; do not claim it reproduces the 2025 graph paper.
- Keep administrative forms, signatures, email screenshots, personal identifiers, credentials, copyrighted papers, and company-confidential material outside the public repository.
- Prioritise reproducibility and controlled research evidence over visible commit volume.

### Current risks and blockers

- The inherited training/testing implementation is not runnable as a trustworthy end-to-end baseline without repair.
- The authoritative GCQN/GCAC code commit and experimental configuration require confirmation from Shreya; the repository linked in the paper does not contain that implementation.
- The upstream repository has no declared licence; reuse and redistribution terms require confirmation.
- Baseline runtime and compute requirements have not yet been measured.
- The central two-timescale coordination mechanism still requires research alignment with Prof. Bhatnagar.

## August 2026

### GCQN/GCAC handover provenance audit: 2 August 2026

- Received the local GCQN and GCAC handover roots and confirmed that they are distinct private directories outside the research repository.
- Created branch `audit/exp-graph-000-provenance` from commit `6a136079835fc3be11cfd549c7ac1faaaa371848`.
- Implemented a read-only, standard-library inventory utility with deterministic private JSON/CSV output, SHA-256 hashing, duplicate detection, same-path comparison, unreadable-file reporting, and root-versus-nested Git-marker summaries.
- Added six synthetic unit tests covering determinism, relative paths, symlink handling, output isolation, unreadable files, and embedded Git classification.
- Completed two full inventory passes: GCQN contains 29,184 files totalling 458,999,601 bytes; GCAC contains 13,140 files totalling 341,321,191 bytes; no unreadable entries were found.
- Confirmed 12,906 equal-content files and 210 different-content files at equal relative paths, with 18,609 GCQN-only paths and 30 GCAC-only paths.
- Verified all seven outputs were byte-for-byte deterministic across the two runs and that no absolute local paths appeared in the 14 generated private files.
- Static provenance checks established that GCQN has incomplete root Git provenance because its recorded `HEAD` does not resolve, while GCAC has no root Git marker. Both contain nested Git metadata; no runtime conclusion was drawn.
- Produced the aggregate public audit and `EXP-GRAPH-000` record without modifying handover code, installing dependencies, running training, or copying private artifacts into Git.

### GCQN/GCAC foundational semantic audit: 2 August 2026

- Created branch `audit/exp-graph-001-semantic-map` from the reviewed `main` milestone.
- Audited paper Sections 2.1-3.3 and Algorithms 1-2 against both private handovers without importing or executing either codebase.
- Created a private line-level evidence matrix outside Git covering 27 MDP, GCQN, and GCAC semantic items.
- Classified 8 items as mapped, 7 as partial, 7 as apparent conflicts, 4 as missing, and 1 as unverified; every item still requires runtime verification.
- Recorded strong static correspondences for graph construction, phase transitions, GCQN target updates, GCAC policy/value structures, actor and critic losses, and gradient-based updates.
- Recorded apparent conflicts in state aggregation, reward construction, GCQN action/loss behavior, replay lifecycle, GCAC action selection, GCAC discount-factor notation, and on-policy semantics.
- Confirmed that terminal handling is not visible on either candidate learning path.
- Published only sanitized aggregate findings in the research map and `EXP-GRAPH-001` record; no private evidence or reproduction claim entered Git.

### GCQN/GCAC dispatch and symbolic shape audit: 7 August 2026

- Continued `EXP-GRAPH-001` on branch `audit/exp-graph-001-dispatch-shapes` from the reviewed `main` milestone.
- Traced runner, configuration, registry, task, trainer, environment, agent, replay, graph model, loss/update, target-network, evaluation, and checkpoint-loading dispatch without importing or executing either handover.
- Created a private line-level dispatch/shape matrix outside Git and a sanitized public audit using symbolic dimensions `N`, `E`, `F`, `A`, `B`, and `K`.
- Identified a scalar/single-intersection graph-Q path and a full-network node-wise graph-Q path as competing selectable GCQN candidates; neither was classified as historical or authoritative.
- Recorded apparent graph-batch mismatches in the full-network GCQN and GCAC candidates because constructed batched edges are not used by their visible training calls.
- Recorded an apparent GCAC partial return update: the return vector is node-expanded while only a batch-sized prefix is explicitly assigned.
- Confirmed statically that terminal values are not preserved in replay, GCQN target Q-networks are connected to the standard trainer paths, and GCAC target-network use is confined to a competing alternate method with no standard caller.
- Recorded evaluation and checkpoint-loading ambiguity without making runtime, reproduction, performance, or successful-loading claims.
- Kept private filenames, paths, line references, excerpts, configurations, scenario sizes, hashes, and artifact identifiers outside the public repository.

### Generic runtime-probe isolation harness: 7 August 2026

- Created branch `plan/exp-graph-002-runtime-probes` from the reviewed `main` milestone.
- Implemented a Python-standard-library harness that runs one probe per isolated CPU-only subprocess with a configurable timeout and temporary working directory.
- Added explicit allowed-write roots, Python audit-hook write rejection, nested-process and network blocking, and sanitized output and structured results.
- Added stable pass, fail, inconclusive, and blocked statuses together with elapsed-time, exit-status, shape, and call-count evidence fields.
- Added deterministic generic synthetic-world fixtures without copying or mirroring private handover classes.
- Added ten synthetic tests covering successful execution, timeout handling, blocked and allowed writes, network and nested-process blocking, sanitization across every result channel, stable result schema, dependency independence, and deterministic fixtures.
- Kept Stage 1 independent of private handover imports, research dependencies, simulators, models, checkpoints, training, and algorithm repair.

### Compute-environment decision documentation: 8 August 2026

- Recorded a public-safe development-host snapshot and its role in editing, orchestration, documentation, analysis, plotting, and standard-library harness work.
- Established separate environment roles for development, reconstructed compatibility validation, canonical dissertation experiments, and optional exploratory compute.
- Documented the existing native Linux x86-64, CPython 3.10.13, PyTorch 1.11.0+cpu compatibility candidate and changed its future execution strategy to dedicated native remote or cloud infrastructure.
- Defined the infrastructure, software, configuration, seed, code, and data identities required for canonical dissertation experiments.
- Separated architecture-independent compatibility evidence from native training and performance evidence.
- Classified managed notebook services as exploratory or supplementary compute and bounded remote workspaces as possible development or compatibility options rather than canonical experiment platforms.
- Deferred provider, machine, GPU, and additional-hardware selection until baseline profiling and cloud-cost evidence are available.
- Completed documentation only; no environment was provisioned, software installed, private handover imported, simulator started, checkpoint loaded, or runtime probe executed.

### Native Linux compatibility environment and dependency validation: 8–9 August 2026

- Created a separate AWS account for dissertation research on the Free plan and hardened access: enabled root MFA while retaining zero root access keys; created the non-root `research-admin` IAM identity with MFA and no access keys; reduced the `research-admins` group to `AdministratorAccess` by removing redundant service-specific administrator policies; and successfully simulated the EC2, IAM, and SSM permissions required for the validation workflow.
- Created disposable EXP-GRAPH-002 infrastructure comprising an EC2 SSM role/profile with `AmazonSSMManagedInstanceCore`, a dedicated zero-inbound security group, no SSH key or port 22, required IMDSv2, and a four-hour automatic-shutdown safeguard.
- Provisioned one On-Demand `m7i-flex.large` instance in `ap-south-1` using the public Canonical Ubuntu 22.04 x86-64 AMI current at execution time and a 40 GB encrypted gp3 root volume. This instance is compatibility-validation hardware only, not canonical dissertation performance hardware.
- Captured the observed runtime identity: Ubuntu 22.04.5 LTS, kernel 6.8.0-1061-aws, glibc 2.35, x86_64, 2 vCPUs, approximately 7.6 GiB usable RAM, Intel Xeon Platinum 8488C, KVM, base Python 3.10.12, and a working SSM Agent.
- Built CPython 3.10.13 from official source under `/opt/exp-graph-002`, created the isolated `venv-l1`, validated native standard-library imports, and recorded source SHA-256 `5c88848668640d3e152b35b4536ef1c23b2ca4bd2c957ef1ecbb053f571dd3f6`.
- Installed and exact-version-audited the selected public L1 dependency closure: PyTorch 1.11.0+cpu, PyG 2.0.4, torch-scatter 2.0.9, torch-sparse 0.6.13, NumPy 1.21.5, Gym 0.23.1, and PFRL 0.3.0. `pip check` reported no broken package requirements.
- Characterized an API-compatibility issue: top-level `import pfrl` fails with Gym 0.23.1 because PFRL 0.3.0 imports the removed `gym.wrappers.Monitor`. This is a reconstructed-environment compatibility result, not a confirmed defect in the historical handover or paper environment.
- Completed an isolated graph-stack validation excluding PFRL: Python 3.10.13, Torch 1.11.0+cpu, PyG 2.0.4, torch-scatter 2.0.9, and torch-sparse 0.6.13 ran CPU-only with CUDA unavailable; a generic `GCNConv` accepted input shape `(3,3)` and edge-index shape `(2,4)`, produced finite output of shape `(3,2)`, and passed its smoke test.
- Stopped all instances after each bounded stage. No private GCQN/GCAC handover was uploaded or executed, and no simulator, checkpoint, training, or paper-performance reproduction was run.
- Research significance: the reconstructed native Linux Torch/PyG graph stack is independently executable, while the PFRL/Gym pair exposes a separate compatibility ambiguity that should be resolved only if the relevant inherited execution path requires PFRL. These results characterize the selected compatibility environment and do not reproduce Shreya's historical environment.

### Candidate N L1 probe validation and import diagnostics: 10 August 2026

- Implemented an isolated, model-only probe for the Candidate N `GCN` using a deterministic synthetic graph with `N=3`, `E=4`, `F=3`, and `A=2`. The probe is CPU-only and excludes simulators, PFRL, agents, replay, training, backward passes, optimizers, and checkpoints.
- Applied bounded execution controls of 60 seconds wall time, 30 seconds CPU time, a 4 GiB address-space limit, and one CPU thread. Synthetic/local validation passed, and the initial freeze passed 25 tests before merging through PR #7 at merge commit `97df49a1f985c20ffb8be58b08edde29a38203b5`.
- Validated the merged probe on the native Linux x86-64 compatibility environment with CPython 3.10.13, PyTorch 1.11.0+cpu, PyG 2.0.4, torch-scatter 2.0.9, and torch-sparse 0.6.13. Linux enforced the 4 GiB `RLIMIT_AS`, and the synthetic Candidate N probe passed under the production isolation controls without private source; the instance was stopped afterward.
- Performed the first controlled private Candidate N L1 characterization using only the approved minimum source subset with encrypted, non-public temporary staging and RAM-backed, read-only exposure. Source integrity was verified before and after execution, temporary permissions and staged data were removed, and the instance was stopped.
- Recorded the private characterization as `INCONCLUSIVE`: containing-module execution failed before normal `GCN` lookup, so model construction and forward execution were not reached. PFRL and traffic simulators were not loaded, and no training, backward pass, optimizer, or checkpoint operation occurred. This is an import-isolation ambiguity, not evidence of a model or algorithm defect.
- Diagnosed that the loader required successful execution of the complete containing module before class lookup. The immediate limitation was insufficient sanitized observability; available evidence did not justify another stub or any change to Candidate N computation.
- Added sanitized import diagnostics for exception class, import-stage classification, contextual last import root, and `GCN` visibility at failure. No new stubs or model-boundary changes were introduced, and a partially defined `GCN` is never executed. All 29 tests passed before merging through PR #8 at merge commit `8f66636bde90e9758113fc7b53f4702593372a26`.
- Research significance: the infrastructure, dependency stack, Linux resource limits, isolation controls, and private-source lifecycle are experimentally validated. Candidate N model-level compatibility remains unresolved because forward execution has not yet been reached; the exact import boundary must be diagnosed before changing the isolation boundary.

### Candidate N L1 reproducibility and TD/update contract characterization: 15 August 2026

- Used the merged sanitized import diagnostics in one controlled private AWS rerun. The previous import failure did not recur: whole-module import completed, `GCN` resolved, model construction and forward execution completed, and the probe returned `PASS`. PFRL and traffic-simulator modules remained unloaded; no agent, replay, training, backward, optimizer, simulator, or checkpoint path was executed. Private-source integrity and cleanup passed. The cause of the earlier `INCONCLUSIVE` remains unresolved; that result was retained rather than discarded.
- Completed an independent confirmation using the unchanged repository revision, compatibility environment, private source, stubs/loader, graph, seeds, and resource limits. It independently returned `PASS` for input `[3,3]`, edge index `[2,4]`, Q output `[3,2]`, greedy-action shape `[3]`, finite output, repeated-forward determinism, and fixed-seed reconstruction determinism, without loading PFRL or a traffic simulator. Candidate N model-level compatibility and deterministic structural forward behavior are therefore repeatably supported within this frozen bounded protocol and reconstructed compatibility environment only. The first private run remains `INCONCLUSIVE`, its cause remains unresolved, and two subsequent unchanged private runs independently passed.
- Reconstructed the visible Candidate N update path statically without executing it. The visible source statically indicates replay storage of current/next state, phase, node-wise actions, and rewards; batching into `[BN,F]` features and `[BN]` actions/rewards; target-network bootstrapping with `r + gamma * max_a Q_target(s', a)`; and no retained `done` value or terminal mask in the visible replay/update path. Current-state online predictions form a detached target matrix in which only each selected-action cell is replaced, loss is MSE over the complete `[BN,A]` matrices, and target synchronization is a hard online-to-target state copy.
- Recorded a source-level graph-batching observation for the designed `B=2`, `N=3`, `E=4` case: batching constructs an edge index `[2,8]`, while the visible GCN instances retain the original `[2,4]` edge index when receiving concatenated `[6,3]` features. This requires runtime characterization and is not a confirmed defect.
- Designed, but did not execute, a bounded synthetic TD/update-contract probe with `B=2`, `N=3`, `E=4`, `F=3`, and `A=2`, deterministic real online/target GCN outputs, hand-computable TD targets, and expected scalar full-matrix MSE loss `3.355`. The design excludes a real simulator, PFRL, backward propagation, optimizer mutation, and extended training; it is not runtime evidence.
- Established the permission boundary for the proposed experiment: it requires executing Candidate N agent/update methods. Although the same combined private component may be sufficient physically, its executable scope would expand beyond the approved model-only compatibility test. Existing cloud permission is therefore insufficient, and new narrowly scoped approval is required before any AWS agent/update execution; no such approval has yet been obtained.
- Research boundary: the completed evidence supports repeatable Candidate N model-only forward behavior within the frozen protocol and a sufficiently characterized static update contract for designing the next bounded experiment. It does not establish paper reproduction, the historical execution path or environment, agent/update runtime correctness, terminal-aware learning, replay graph-message-passing correctness, backward/optimizer correctness, simulator integration, training stability or convergence, traffic-control performance, or superiority.

### August 2026 entry goals

- Publish the preservation tag and repository-foundation changes after review.
- Confirm code provenance, licence expectations, and the authoritative GCQN/GCAC repository with Shreya.
- Create the first milestone branch for deterministic DQN reproduction.
- Specify supported Python, PyTorch, SUMO, and dependency versions.
- Repair registered layers, device handling, observation/reward consistency, terminal transitions, and evaluation loading.
- Add deterministic seeds and automated smoke tests.
- Establish fixed-time or round-robin comparison and record first multi-seed runtime/results.
- Prepare a one-page research roadmap for Prof. Bhatnagar's alignment on hypothesis, contribution, and evaluation gates.

---

## Monthly entry template

### Completed work

- 

### Research questions and decisions

- 

### Mentor guidance

- 

### Experiments

- **Experiment ID:**
- **Question/hypothesis:**
- **Commit and configuration:**
- **Scenario and seeds:**
- **Environment and hardware:**
- **Result:**
- **Interpretation:**
- **Decision/next action:**

### Evidence produced

- 

### Risks and blockers

- 

### Next-month goals

- 
