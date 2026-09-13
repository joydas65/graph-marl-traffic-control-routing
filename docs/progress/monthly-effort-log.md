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

### Candidate N synthetic binding validation and execution-package freeze: 17 August 2026

- Implemented the bounded Candidate N agent/update-contract observation architecture incrementally. Synthetic stand-ins independently validated replay and batching, deterministic action selection, TD/loss observation, controlled post-loss stopping, isolated hard-target synchronization, and passive graph-edge observation. The components were then integrated through the frozen public `run_integrated_contract(...)`; the synthetic integration supported deterministic repeatability, conservative status propagation, lifecycle cleanup, and separation of model-setup, update, and synchronization mutation scopes.
- Developed a private-local, production-shaped loader/isolation scaffold enforcing single-component scope, a read-only regular-file and non-symlink policy, before/after integrity comparison, constrained symbol resolution, dependency boundaries, and exact inert-boundary handling. Production private loading remained disabled throughout.
- Developed production-shaped bindings for controlled subject/model construction, constructor bypass, deterministic model setup, replay/storage/batching, action selection, hard-target synchronization, TD/loss/update observation, the post-loss optimizer guard, and passive graph-edge observation. These definitions were validated with synthetic loaded-component handles only; no real private Candidate N component was loaded or executed.
- Integrated all loader and binding definitions through the frozen public runner. The integrated synthetic contract passed with deterministic repeatability; `FAIL`, `INCONCLUSIVE`, and `BLOCKED` early-stop behavior was exercised across every major binding stage, and cleanup and mutation-scope isolation passed. The complete private-local validation suite passed 243 tests, and the frozen public regression suite passed 55 tests.
- Froze the authored private execution machinery as a private, read-only, integrity-recorded package labelled `EXP-GRAPH-002-CANDIDATE-N-UPDATE-ADAPTER-V1`. The package contains no Candidate N private source; digest values and private package metadata remain outside the public repository. Production private loading remains disabled, and no AWS or private-source execution occurred during this checkpoint.
- Research boundary: this work supports synthetic validation of the execution machinery and production-shaped Candidate N binding definitions against the frozen bounded contract. It does not establish actual Candidate N agent/update runtime compatibility, paper or historical-environment reproduction, training or terminal-handling correctness, graph-batching correctness, simulator compatibility, convergence, performance, or superiority over baselines.

### Candidate N V2 blocked execution, diagnosis, and V3 correction: 21 August 2026

- Completed the first bounded private Candidate N agent/update attempt after all pre-source cloud gates passed. Exactly one approved source component was staged securely, and the single-use activation was consumed once; execution returned `BLOCKED` before the private component loaded, so replay, action, TD/loss, synchronization, and graph-observation paths were not reached. No backward pass, optimizer update, simulator, training, or retry occurred. Source integrity and mandatory cleanup passed. The preserved result is `CANDIDATE_N_PRIVATE_UPDATE_CONTRACT=BLOCKED`, which does not establish Candidate N incompatibility.
- A targeted static diagnosis identified an overly strict relative-import policy: module definition required one level-one relative import of its base class. The subsequent base-agent contract audit established that Candidate N directly defines the learning-relevant replay, batching, action, update, and target-synchronization behaviour required by the bounded experiment; real base-agent execution is therefore unnecessary, and one-component source scope remains sufficient. This supersedes the earlier inference that replay storage might be inherited.
- Corrected only the loader boundary by adding a virtual parent-package context and permitting exactly one reviewed relative-import edge. The base-class alias remains inert and supports class definition only; real package-initializer execution, neighbouring or arbitrary private imports, and other relative imports remain prohibited. Default-deny, explicit, single-use activation and one-component scope were preserved.
- Froze the corrected V3 execution package with a private integrity record. The combined frozen private suite passed 301 tests, the public regression suite passed 55 tests, and the integrated production-shaped synthetic contract passed. V2's prior `BLOCKED` provenance remains preserved. V3 contains no Candidate N private source, and no cloud or private-source execution occurred during V3 development or freezing.
- Research boundary: V3 establishes synthetic validation of the corrected loader, binding, activation, and bounded execution machinery only. It does not establish successful real Candidate N loading, real update-contract compatibility, paper reproduction, training or simulator correctness, convergence, or performance.
- Permission boundary: the first private-execution authorization was consumed. Renewed narrow authorization has now been obtained for exactly one additional bounded execution using the same one-component source scope and frozen V3 package. The second execution has not occurred, and its cloud environment has not been started; authorization remains limited to encrypted, non-public, read-only handling, the synthetic bounded agent/update contract, no simulator, training, backward pass, or optimizer mutation, and immediate verified source deletion afterward.

### Candidate N V3→V4 late-August research checkpoint: 22–30 August 2026

- Closed the later-August documentation gap; work through 21 August was already recorded in the preceding checkpoints.
- Added the consolidated [Candidate N V3→V4 research checkpoint](../research/candidate-n-v3-v4-august-2026-checkpoint.md) with explicit synthetic, private-static, runtime-evidence, supersession, and claim boundaries.
- Recorded the V3 source-free validation outcome of 301 V3 tests passed, 55 public regression tests passed, and zero collection errors, together with the corrected native source-lifecycle gate.
- Preserved the later renewed execution outcome as `BLOCKED`: it stopped before private-source upload, capability creation, private loading, or Candidate execution because no frozen reviewed end-to-end driver existed. The remaining authorization was not consumed.
- Established statically why V3 could not honestly preserve primary replay/update continuity without direct Candidate invocation or manufactured replay state, motivating a V4 successor rather than an algorithm repair.
- Resolved a shared-primary replay/update coordinator contract while retaining isolated terminal, action, synchronization, and graph observations and leaving the frozen public runner unchanged.
- Reduced the admissible future real-runtime evidence to directly observable values; bootstrap maxima and hidden temporal-difference matrices remain synthetic-only.
- Reconciled the two permitted replay orders and fixed the primary full-matrix mean-MSE endpoint oracle at `43.88`; `3.355` remains specific to the earlier synthetic fixture.
- Resolved static reader, activation/C2 cleanup, controller receipt/status, strict mapping, and durable write/readback contracts without implementing them.
- Recorded authorized read-only static findings that Candidate N owns exact genuine RMSprop and mean-reduced MSELoss, superseding the earlier SGD provider proposal.
- Recorded pre-guard compatibility with temporary optimizer-slot replacement and a transparent criterion wrapper; no backward or optimizer-step compatibility is claimed.
- Disclosed the P1 component-identification scope-selection deviation and its immediate stop/non-use; P2 had no scope deviation.
- A subsequent 30 August static reconciliation completed the subject-role/model-setup topology across six controlled subjects and independently owned sessions: six controlled-subject state setups, four model-bearing roles and role-level deterministic model setups, four online plus two target models, six model-builder calls and parameter-configuration applications, two replay-only terminal setups, and four replay containers owned by the primary, terminal-false, terminal-true, and graph roles.
- Reconciled the single C2-owned run-scoped provider lease, four non-owning role-restricted facets, role-specific mutation baselines and cleanup, and V1 lifecycle-receipt applicability; terminal roles receive no provider handle, and never-acquired resources remain `NOT_APPLICABLE_NOT_ACQUIRED`.
- Left the external controller host, native filesystem primitive, security/receipt review, V4 implementation, integrated validation, and later authorization reconfirmation unresolved.
- Research boundary: V4 remains unimplemented and not ready to implement; this documentation task performs no AWS or private-source activity and makes no training, simulator, performance, superiority, historical-environment, or paper-reproduction claim.
- Next gate: `SELECT_AND_REVIEW_V4_EXTERNAL_CONTROLLER_HOST_AND_RECEIPT_CHANNEL`.

### August 2026 entry goals

- Publish the preservation tag and repository-foundation changes after review.
- Confirm code provenance, licence expectations, and the authoritative GCQN/GCAC repository with Shreya.
- Create the first milestone branch for deterministic DQN reproduction.
- Specify supported Python, PyTorch, SUMO, and dependency versions.
- Repair registered layers, device handling, observation/reward consistency, terminal transitions, and evaluation loading.
- Add deterministic seeds and automated smoke tests.
- Establish fixed-time or round-robin comparison and record first multi-seed runtime/results.
- Prepare a one-page research roadmap for Prof. Bhatnagar's alignment on hypothesis, contribution, and evaluation gates.

## September 2026

### Candidate N V4 controller-provisioning Module A public projection: 2 September 2026

- Published the public, source-safe `CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_A_V1` finite-state contract and its exhaustive standard-library unit tests.
- Fixed the exact three-phase condition truth table, twelve-resource registry, eight persistent-resource invariant, three legal forward transitions, legal resource deltas, sealed-state metadata expectation, deterministic ordering, immutable derived records, and exact clarification-version binding.
- Added a research note that separates the implemented specification from future template construction and live infrastructure validation.
- Kept the implementation independent of provider SDKs, external dependencies, simulators, model execution, evidence writing, and cloud API calls.
- Verified all 53 dedicated Module A tests and all 108 repository tests with both the established standard-library discovery command and the host-side Pytest runner; compilation and whitespace checks also passed.
- Research boundary: this is reviewed provisioning apparatus, not a deployable template, a provisioned controller, graph-MARL novelty, runtime evidence, traffic-performance evidence, or paper reproduction. Module B remains a separate future publication gate.

### Candidate N V4 controller-provisioning Module B public projection: 3 September 2026

- Published the public, source-safe `CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_B_V1` structural model and offline validator with an exact import-time binding to public Module A and the phase clarification.
- Fixed three non-deployable main profiles and two non-deployable staging profiles, the exact twelve-resource type/Condition model, active counts of eight, twelve, and ten, retained-evidence attributes, the three-edge dependency graph, bootstrap expectations, and closed privileged-content deferrals.
- Added compact canonical UTF-8 JSON rendering, duplicate and non-canonical input rejection, a closed-result validator, a bounded accidental-leakage scanner, twenty-six named in-memory negative fixtures, and a 5,000-cycle independent determinism check.
- Verified all 53 Module A regression tests, all 72 Module B tests, and all 180 repository tests with standard-library discovery; the Pytest run also passed all 180 tests and 249 subtests. Compilation, direct execution of the Module B test file, whitespace checks, public dependency review, and the context-aware privacy review passed.
- Research boundary: Module B remains an AWS-independent structural specification, not deployable CloudFormation, an IAM/KMS or bootstrap implementation, controller provisioning, live infrastructure evidence, Candidate runtime evidence, traffic-performance evidence, paper reproduction, or Module C.

### Candidate N V4 controller-provisioning Module C public projection: 4 September 2026

- Published the public, source-safe `CANDIDATE_N_V4_CONTROLLER_PROVISIONING_MODULE_C_CHANGESET_REVIEWER_V1` offline semantic reviewer with exact bindings to public Modules A and B and the phase clarification.
- Implemented normalized, immutable review contracts for S0, M0, S1, M1, and M2; A/B-derived expected mutations; order-independent comparison; complete-page-set and protected-resource gates; and deterministic `ACCEPTED` or `BLOCKED` results with closed reasons.
- Preserved the strict update contracts: S1 changes only the staging bucket policy, M1 adds exactly the four compute/bootstrap resources, and M2 removes the two bootstrap resources and performs only the required non-replacing controller metadata modification.
- Published 64 named negative-fixture semantics, 105 systematic mutation cases, semantic-duplication checks, and repeated mixed-operation determinism. Artificial sensitive-shaped scanner inputs are assembled at runtime from harmless fragments, so no credential-shaped test literal or real cloud identifier is committed.
- Verified all 53 unchanged Module A tests, all 72 unchanged Module B tests, and all 239 Module C tests. The full Pytest repository suite passed 419 tests and 249 subtests, and standard-library discovery passed its 180-test surface. Compilation, whitespace, dependency, privacy, and synthetic-secret scans also passed.
- Research boundary: Module C reviews normalized offline descriptions only. `ACCEPTED` is not an AWS or provisioning approval and does not establish service-pagination correctness, AWS acceptance, IAM/KMS correctness, provisioning readiness, Candidate behavior, traffic performance, paper reproduction, or methodological superiority.
- Next gate: reassess whether remaining controller-provisioning apparatus or simulator-integrated empirical work offers the greater reduction in dissertation research uncertainty.

### Pre-empirical research charter and novelty audit: 4 September 2026

- Deliberately parked Candidate N and froze the narrower empirical research question around capacity-conditioned graph communication under localized road-capacity reductions.
- Published a versioned pre-treatment charter covering the central and secondary hypotheses, B0–B3/T0 baseline hierarchy, A0–A3 ablations, physical-location split, outcomes, guardrails, statistical principles, mechanism diagnostics, failure criteria, and conditional routing gate.
- Completed a bounded public-source literature collision audit. No near-duplicate was located through 4 September 2026; this is not an absolute novelty claim.
- No capacity-conditioned treatment was implemented or evaluated, and no experimental result was created at this checkpoint. The next empirical step is one deterministic fixed-time SUMO baseline on the smallest selected network with a versioned scenario, seed, and metric record.

### B0 fixed-time substrate and 1X exposure diagnosis: 4 September 2026

- Generated and froze `B0_GRID_3X3_V1`, a 3×3 network with nine controlled intersections, twelve fixed row/column routes, 180 trips over `[0,900)`, static 68-second TLS programs, and a 1,500-second pilot horizon.
- Executed fixed-time N0/D0 and exact repeats at seed `20260904`; all 180 trips completed in every run with zero teleports, collisions, invalid routes, or unfinished trips. Metric, trace, ledger, and event-lifecycle repeat comparisons passed.
- Independently reconciled scheduled-trip accounting, restricted mean and P95 trip time, queue burden, native waiting, throughput, and disruption application against raw evidence without changing the scenario.
- Validated a read-only per-vehicle exposure observer and its noninterference contract. Five vehicles entered `A1B1` during the event, all used surviving lane `A1B1_1`, and no passenger entered restricted lane `A1B1_0` after activation.
- Recorded `B0_EMPIRICAL_SUBSTRATE_VALIDATED=YES` while retaining the distinct scenario verdict `TOO_WEAK`: N0/D0 restricted mean and P95 trip times were identical, queue burden differed by only −1 vehicle-second, and no exposed vehicle incurred additional edge or arrival delay.
- Published only generated inputs, exact source provenance, tests, and compact results. Raw simulator outputs and machine-specific receipts remain ignored; no RL, treatment, OD calibration, or central-hypothesis test occurred.

### B0 uniform-demand calibration and publication: 4–5 September 2026

- Froze a baseline-only first-qualifying calibration contract over 2X, 3X, 4X, and 5X globally balanced traffic at the calibration-seen `A1B1`/`B1A1` corridor, using calibration seeds `20260904`, `20260905`, and `20260906`.
- Preserved attempt 1 as a pre-SUMO local connection failure with no observations; attempt 2 retained the scientific inputs and completed all 24 fixed-time N0/D0 simulations.
- All 12 seed pairs passed integrity and completion checks, but all definitively failed both network-response gates. The 2X/`20260906` pair also fell below the exposure gate. No level qualified on all three seeds.
- Recorded `CALIBRATION_STATUS=NO_QUALIFYING_DEMAND_LEVEL`, `SELECTED_CALIBRATED_DEMAND_LEVEL=NONE`, and `DISSERTATION_EFFECT_THRESHOLD_REMAINS_UNSET=YES`. No deterministic repeat or calibrated-scenario freeze was performed.
- Published the frozen contract, exact executed-source provenance, 35 logic tests, demand identities, and concise aggregates while excluding the 550-artifact raw evidence tree and machine-specific receipts.
- Across the frozen 2X–5X ladder, globally balanced density did not meet the predeclared network-response gates. The +1-second and +5% pilot gates were not dissertation δ, which remains unset. The single next baseline-only axis is OD/corridor concentration at fixed 3X total demand; no such run, RL, routing, graph method, treatment, or central-hypothesis test occurred here.

### B0 OD-concentration protocol and corrected V2 public checkpoint: 5 September 2026

- Prepared the minimum public [pre-run protocol and implementation checkpoint](../experiments/EXP-B0-OD-001.md): byte-exact Scientific Contract V1, deterministic OD generation, the corrected V2 measurement adapter, and self-contained offline tests.
- Preserved the fixed 540-trip budget, all twelve seed/concentration assignments, departure schedule, nested target sets, qualification rules and stopping budget. No concentration has been selected and dissertation delta remains unset.
- Recorded the V1 defect: two individually finite native waits could overflow their accumulated total while the result remained `VALID`. V2 returns an explicit integrity failure and null total, retains every trip, and guards other floating metrics. Historical artifacts and the separately recorded V1 failing assertion remain unchanged.
- Kept production projection changes to one observer-path expression; OD source and scientific contract are byte-identical to their freezes. Public fixtures reconstruct inputs and use recorded synthetic-output identities without importing defective V1 or reading ignored workspaces.
- Verified 153 B0 offline tests: 88 original adapter cases, 13 correction cases, two public-projection cases and 50 unchanged public regressions; zero failures/errors/skips/collection errors, with 175 subtest callbacks separately counted. Compilation, complete/censored compatibility, strict JSON, twelve input readbacks and public dependency checks passed. No process/socket/simulator or ignored-workspace access was attempted by the guarded tests.
- Research boundary: this is a draft-review checkpoint, not independent external approval, a live writer, simulator integration, OD-calibration evidence or a dissertation-treatment result. Independent public-source review remains the next gate; no merge, simulation, AWS, private-source execution, RL or routing work occurred.

### Repository publication privacy hygiene: 6 September 2026

- Added the [sanitation and local publication-privacy note](../decisions/0003-repository-publication-privacy.md), distinguishing freshly rechecked Git-object invariants from receipt-reported historical verification and accessibility. This is repository hygiene, not scientific progress.
- Added one standard-library checker and thin pre-push entry point: fixed-checkpoint trust, superseded-history rejection, raw author/committer and message checks, all outgoing commit trees, bounded text inspection and sanitized fail-closed outcomes. No historical identity or private mapping is embedded in public fixtures.
- Verified 46 focused offline tests with zero failures, errors, skips or collection errors; 28 subtests were counted separately. Tests use synthetic temporary Git repositories, including a filesystem-only bare remote that demonstrates Git invoking the hook and rejecting an unsafe push. Exact-blob review for one unchanged historical synthetic home-path fixture does not exempt private-value, credential or metadata checks. No scientific suite or simulation ran.
- Installed the reviewed snapshot and private policy only in this checkout's Git common directory after confirming no custom hooks path or existing pre-push hook. All fourteen pre-existing hook files retained their bytes and permissions. Clones do not automatically inherit activation, and existing hook arrangements require review rather than replacement.
- Prepared a private read-only plan for four local and two remote retained branches. Mapped-content comparison found no unique work, active worktree use or open-PR association for these targets; proposed dispositions still require fresh exact-ref authorization. No retained ref was modified, and complete historical erasure remains unestablished.
- Preserved all eight historical SHA references, B0/OD sources, tests, contracts and results. Live integration and the output writer remain absent, OD calibration has not run, no concentration is selected, dissertation delta remains unset, and readiness remains false. The next gate is review of the hygiene PR and private retained-ref plan, followed by a return to the minimal OD integration layer.

### Minimal B0 OD integration public pre-run checkpoint: 6 September 2026

- Prepared the [offline integration checkpoint](../experiments/EXP-B0-OD-002.md) with three production modules, focused public tests and exact source/dependency projection identities. At the initial public checkpoint, the integration and qualification sources were byte-identical to their validated originals; the writer changed only its isolated output-root expression.
- Preserved Scientific Contract V1, Adapter V2, all twelve 540-trip allocations, measurement definitions, qualification precedence, first-qualifying/repeat rules and the future 24-plus-two simulation budget. Historical snapshots remain unchanged.
- Verified 74 public integration tests and 94 subtests, plus 153 unchanged B0/adapter tests and 175 subtests, with zero failures/errors/skips/collection errors and zero forbidden-access attempts. The original 72-test surface remains intact; two publication checks add source/import identity and explicit oversize rejection.
- Preserved the technical history of the initial 32 MiB writer-limit failure and its existing 64 MiB correction. The full 26-record synthetic fixture measures 56,899,689 bytes and passes actual write, independent hash/readback and finalization; this is not a traffic result or execution of the scientific budget.
- Research boundary: thin live binding absent, no simulation or OD calibration, no selected concentration, dissertation delta unset, Candidate N parked and readiness false. Independent public-source review is pending; this checkpoint authorizes no merge or live validation. Historical privacy cleanup remains incomplete.

### PR #23 operational-status correction: 6 September 2026

- Reproduced the reviewed first-advance OSError with actual integration functions and the existing fake backend: TECHNICAL first failure, unusable measurement, successful cleanup, but pair/session FAIL caused by absent full-horizon evidence. This is synthetic review evidence, not a SUMO result.
- Added bounded unchanged-clock step-abort readback and verified-prefix assessment. Supported operational interruption now propagates BLOCKED through pair/session/repeat and failure persistence; partial measurement remains unusable and independent contradictions retain FAIL precedence. No scientific gates, allocations, measurement definitions, thresholds, budget or writer completion protocol changed.
- Final validation passed 12 focused tests/38 subtests, 86 full public integration tests/134 subtests and 153 existing tests/175 subtests, with zero failures/errors/skips/collection errors, stable source hashes and no forbidden-access attempts. The focused suite is included in the full suite. The original reports and an earlier passing development run are preserved separately.
- Updated the [checkpoint](../experiments/EXP-B0-OD-002.md) and projection manifest to distinguish original, initial-publication and corrected identities. All three corrected production modules differ from the original snapshot; path-only/byte-identical statements now describe only the initial historical publication. The 56,900,339-byte full synthetic fixture passes the unchanged 64 MiB writer limit.
- Boundary: only evidenced unchanged-clock step aborts are supported by this correction; setup/permission/ambiguous aborts are not blanket-reclassified. No live integration, simulation, calibration, cloud, RL, routing or treatment work. PR #23 must remain draft/unmerged; next gate is REVIEW_PR23_OPERATIONAL_STATUS_CORRECTION_BEFORE_MERGE.

### Thin B0 OD live-binding compatibility gate: 6 September 2026

- Started from merged checkpoint `c0be5ca5c0116179f901bd00410c74e581799c87` on one new local feature branch. Static integration/client inspection and synthetic checks identified a terminal-finalization status-contract incompatibility; production implementation stopped under the task's explicit scope gate.
- Added a [focused stop note](../experiments/b0-od-live-binding-v1-stop-note.md) and seven synthetic characterization tests/four subtests through the actual accounting, pair and strict writer/readback boundaries. Passing these tests confirms unsupported behavior, not live-binding acceptance or a SUMO result.
- Re-ran the accepted integration suite (86 tests/134 subtests) and existing B0/adapter suite (153 tests/175 subtests). All three surfaces passed with zero failures/errors/skips/collection errors or forbidden-access attempts and unchanged checked source hashes; in-memory compilation and whitespace checks passed.
- No accepted source, scientific contract, source-binding manifest, historical evidence, hook, policy or retained ref changed. No simulator/client import, simulator process/socket, calibration, private material, cloud, commit or publication. The proposed next gate requires fresh authorization for narrowly versioned terminal-finalization evidence/status reconciliation; readiness remains false.

### Proposed B0 OD finalization-contract extension: 6 September 2026

- Added one [specification addendum for review](../experiments/b0-od-finalization-contract-extension-v1-proposal.md): a structured finalization boundary, evidence-supported precedence, exact affected call sites, seven-case regression mapping and explicit legacy/version limits. Distinguished the reproducer's injected contradiction flags from independently checked identity evidence.
- Preserved the prior stop note, reproducer and progress entry. No implementation, additional tests, regression rerun, simulator activity or publication occurred. Immediate next gate: `REVIEW_B0_OD_FINALIZATION_CONTRACT_EXTENSION`; the absent thin binding is not ready for publication or execution.

### Reviewed B0 OD finalization extension implementation: 7–8 September 2026

- Implemented the accepted proposal with review amendments on the existing feature branch: explicit schema-2 run/selection/envelopes, integration-owned `collection_state` and parsing, incremental finalization observations, bounded explicitly authorized references, one shared full/prefix validator and propagation through the existing pair/session/repeat/writer boundaries. The [implementation checkpoint](../experiments/b0-od-finalization-extension-v1-implementation.md) records exact changed files, hashes, API and evidence limits.
- Preserved chronological first failure, abort and cleanup records while retaining later supported findings. Independent terminal contradictions now retain FAIL precedence over missing evidence, supported aborts and later acquisition exceptions. Interrupted full collection cannot qualify; a terminal severity label alone cannot replace unavailable support. Invalid assertions are rejected by strict structured persistence, and VERIFIED persistence is never experiment PASS.
- Added explicitly synthetic retained-byte/capture fixtures, exact legacy read-only auditing labelled `LEGACY_FINALIZATION_UNVERIFIED`, mixed-version rejection and finalization-aware independent readback. No archived source was executed or current source hash monkeypatched. The original seven-case characterization and stop note remain byte-for-byte unchanged and are not counted as new acceptance.
- Final frozen-source validation passed 124 combined integration tests/206 subtests and 153 B0/Adapter tests/175 subtests, with zero failures/errors/skips/collection errors, stable source/manifest hashes and no forbidden-access attempts. Compilation, whitespace, document links and all eleven frozen dependency hashes passed. The 56,929,485-byte full 26-record synthetic selection passed the unchanged 64 MiB writer bound and actual write/readback/finalization. Development assertion/loader errors and the reproduced/corrected malformed-finding retention edge are documented separately, not added to final counts.
- Preserved Contract V1, Adapter V2, all allocations, scientific gates, nine repeat families, six exclusions, historical evidence and the future 24+2 simulation budget. Updated current projection identities while retaining original, initial-publication and accepted-checkpoint identities. No commit, staging, push, PR, merge, history rewrite, policy/hook or retained-ref change occurred.
- Boundary: native launcher/transport and SUMO message mapping remain unimplemented; no simulator/client import, live process/socket, OD calibration, AWS, private Candidate material, RL, routing or treatment work. No concentration is selected, dissertation delta remains unset and readiness is false. Next gate: `REVIEW_FINALIZATION_EXTENSION_IMPLEMENTATION_AND_RESUME_THIN_LIVE_BINDING`; not executed here.

### Thin B0 OD plan/collector and explicit native boundary: 9–10 September 2026

- Verified all fifteen reviewed finalization-export files before extending them on the existing feature branch at unchanged HEAD `c0be5ca5c0116179f901bd00410c74e581799c87`. Preserved the prior proposal, implementation report, stop note and historical characterization bytes. User-reported independent review and thirty isolated checks remain distinct from this task's full regression evidence.
- Implemented a deterministic exact-input launch plan, native control/permission normalization with raw observations retained, SUMO 1.27.1-specific diagnostic mapping, schema-2 collection/finalization acquisition and explicit SYNTHETIC/LIVE origins through existing selection/persistence. Added one-shot injected process/transport ownership and cleanup outcomes without implementing native factories or a second scientific stack. The [partial implementation report](../experiments/b0-od-thin-live-binding-v1-implementation.md) records interfaces, exact hashes, source citations and scoped deltas; the [decision record](../decisions/0004-b0-native-representations-and-ownership.md) explains native representations and ownership limits.
- Statically checked installed public client metadata/source and official versioned sources without importing or executing SUMO/TraCI. Pending means delayed insertion; unfinished and undeparted outputs remain distinct; warning text does not automatically mean simulator error. Unsupported diagnostic coverage stays unavailable, and native aborts lacking coverage remain unsupported/FAIL. Actual path/port evidence uses the existing operational exclusion without changing repeat rules.
- Final guarded offline runs passed 210 integration tests/355 subtests and 153 existing B0/Adapter tests/175 subtests, with zero failures/errors/skips/collection errors or forbidden-access attempts and stable source/manifest hashes. Focused subsets are not added to these totals. In-memory compilation, whitespace and all eleven frozen dependency identities pass. The 56,936,193-byte full synthetic selection passes actual write/readback and the unchanged 64 MiB limit. Earlier interrupted development runs and a corrected reason-code compatibility regression are reported separately.
- Concrete unresolved issue: bounded native process/connection acquisition. Passing a timeout to an injected factory does not bound native process creation before a handle exists or the installed client's blocking connect/receive. No native factory was supplied, no full live-binding success is claimed, and no success-next-task recommendation is activated. Server listening scope and real output/callback behavior still require later explicitly authorized native validation.
- Preserved all scientific definitions, 540-trip allocations, thresholds, seeds, nine repeat families, six exclusions and the 24+2 budget. No simulator/client import, simulator process/socket, calibration, AWS/private Candidate, RL/routing, staging, commit, push, PR, merge, policy/hook or retained-ref change. No concentration is selected, dissertation delta remains unset, Candidate N remains parked and `READY_TO_RUN=NO`.

---

### Concrete B0 OD native factory: 10 September 2026

- Completed the narrow native acquisition gap in three new modules: one per-run supervisor/worker session with independently verified READY/GO ownership, a concrete inherited-scope SUMO factory and a pinned-client transport with actual remaining-budget socket operations. Prior production modules and the reviewed finalization extension remain unchanged. The [current implementation note](../experiments/b0-od-thin-live-binding-v1-implementation.md#native-factory-completion--10-september-2026) records exact entry points, identities and deadline boundaries; the preceding partial checkpoint remains historical.
- Guarded full offline runs passed 310 integration tests/467 subtests and 153 existing B0/Adapter tests/175 subtests, with zero failures/errors/skips/collection errors, no forbidden-access attempts and unchanged source hashes. Focused development subsets are not added to these counts. The 56,943,083-byte synthetic C4 selection passed the unchanged 64 MiB writer and actual readback/finalization. In-memory compilation, whitespace, document links and all eleven frozen dependency identities passed.
- Tests exercise production coordination and actual collector/schema-2 assessment/writer paths with injected OS/IPC/socket/clock doubles, including positive handoff, late FAIL precedence, pre-handle stalls, partial-message deadlines, late handles/results, cancellation, reporting/descriptor failures and scoped cleanup. They establish no actual OS cancellation, socket timing, client compatibility or simulator result.
- Ownership is established before SUMO acquisition, not before initial worker creation. Initial OS bootstrap remains non-interruptible; exclusive worker reaping is an explicit environment requirement. One cleanup deadline bounds exact-scope escalation and worker reaping; forced cleanup without child-wait evidence remains unresolved. Server listening scope and real callback/output behavior await separately authorized native validation.
- Prepared one Git-ignored focused review ZIP with complete changed/new source and tests, relevant untracked files, reports/proposal, source manifest, accepted-base diff and per-file inventory; private material and generated run evidence are excluded. Branch/HEAD and empty index are preserved; no staging, commit, push, PR, merge, policy/hook or retained-ref changes.
- No real helper/SUMO process, native socket/client import, OD calibration, AWS/private Candidate, RL or routing activity. Scientific inputs, allocations, clocks, thresholds, stopping/repeat rules and 24+2 budget remain unchanged. No concentration is selected, dissertation delta remains unset and readiness remains false. Next gate: `INDEPENDENTLY_REVIEW_COMPLETED_THIN_BINDING_BEFORE_PUBLICATION`; not executed here.

### Combined B0 OD finalization/native-binding publication preparation: 12 September 2026

- Prepared one [combined pre-run checkpoint](../experiments/EXP-B0-OD-003.md) on the existing feature branch against unchanged accepted/fetched main `c0be5ca5c0116179f901bd00410c74e581799c87`. Rechecked all 33 reviewed repository files against the preserved exact-identity inventory before publication edits. The ZIP itself is absent from its recorded local location; no fresh archive verification or recreation is claimed. Inventory, focused diff, validation summary and historical reports remain unchanged.
- Recorded the user-reported independent archive source review and 112-test/194-subtest rerun as a limited subset, not the full suite, native execution, formal GitHub approval or faculty approval. Preserved every native-bootstrap, reaper, forced-cleanup, listening-scope and client/helper-closure limitation.
- Made only the authorized finalization opening-docstring correction in production source, verified post-docstring bytes and executable AST unchanged, added publication identity assertions and retained prior source hashes separately from current projection identities. Reviewed excluded navigation/progress changes and corrected current navigation without rewriting historical validation records. The checkpoint enumerates all 37 intended public files; no export archive, bulky output, private policy/mapping or machine receipt is included.
- Fresh complete guarded offline runs passed 310 integration tests/467 subtests and 153 B0/Adapter tests/175 subtests, with zero failures/errors/skips/collection errors or forbidden-access attempts and stable source hashes. The 56,943,083-byte full synthetic selection passed actual write/readback/finalization and the unchanged 64 MiB limit. Compilation, whitespace, source/import identities, documentation links and all eleven frozen scientific dependencies passed. No subset counts are added again.
- Installed-guard ancestry and prospective-content checks passed without policy changes or exceptions. Remote publication is authentication-blocked at this local preparation checkpoint; no draft PR or hosted-content/checks/review result is claimed. The next publication action requires restored access for the intended repository account, followed by the existing guarded normal push and draft-only workflow.
- No native helper/SUMO/socket/client execution, OD calibration, AWS/private Candidate, RL/routing, scientific changes, history rewrite, tag movement or merge. No concentration is selected, dissertation delta remains unset and readiness remains false. The post-publication gate is `FINAL_REVIEW_OF_NATIVE_BINDING_PUBLIC_CHECKPOINT_BEFORE_MERGE`; it has not been executed.

### Evidence-gated native terminal cleanup correction: 13 September 2026

- Implemented the [narrow terminal cleanup correction](../experiments/b0-od-terminal-cleanup-correction-v1.md) from accepted main `215ff23487df71fc1fa4d701e7e7959c43a9cf70`. The original harmless P2 and separately instrumented diagnostic remain FAIL; their sources, reports, receipts and inventories are unchanged. The exact host permission-denial cause remains unresolved.
- Final KILL may be skipped only for the originally verified retained unreaped worker, a complete current run-bound handoff with concrete sole-child wait/finalization agreement, and exact non-reaping terminal-worker evidence without ownership contradictions. Signalling is permanently disabled before consuming reap; missing proof, unsafe ownership, failed/late reap and actual signal errors cannot become cleanup success. Full scientific readback remains after cleanup.
- Final guarded offline validation passed 361 integration tests/536 subtests and 153 existing B0/Adapter tests/175 subtests, with zero failures/errors/skips/collection errors or forbidden-access attempts and stable source hashes. The new 51-test/66-subtest focused suite is included, not added again. An earlier development handoff-vocabulary error was corrected to the existing measurement statuses before freezing.
- In-memory compilation of 28 Python files, whitespace, document links and all eleven frozen scientific dependencies passed. The 56,943,083-byte synthetic C4 selection passed the unchanged writer bound and readback/finalization. Current source/projection identities are updated while prior published identities remain separately recorded.
- Prepared the focused commit/normal-push/draft-only checkpoint under the existing installed privacy guard, without policy changes. No native wait/signal/process/socket revalidation, SUMO, calibration, private Candidate or routing activity occurred. Scientific contracts, thresholds, allocations, historical evidence and the 24+2 simulation budget are unchanged; no concentration is selected, dissertation delta remains unset and readiness remains false. Next gate: `REVIEW_TERMINAL_CLEANUP_CORRECTION_BEFORE_NATIVE_REVALIDATION`; not executed here.

### PR #25 INCONCLUSIVE handoff preservation: 13 September 2026

- Reproduced the independently reported regression on reviewed head `7e1733ad11f2b240f80c942a79fb91c6799c2024`: actual injected worker/collector/assessment/writer produced a completed `EVIDENCE_DEFICIENCY/INCONCLUSIVE` failure record, but both handoff validators rejected it with `WORKER_HANDOFF_ASSESSMENT_SCHEMA`, with and without correlated child-wait closure. The original evidence-deficiency failure and both historical native P2 FAILs are preserved.
- Made the sole production correction by adding the existing `INCONCLUSIVE` stop outcome to the worker's in-memory schema vocabulary. No terminal-cleanup predicate, identity/token/wait requirement, scientific assessment/readback rule, FAIL precedence, qualification, signal policy or native diagnostic mapping changed. The [follow-up record](../experiments/b0-od-terminal-cleanup-correction-v1.md#pr-25-inconclusive-handoff-follow-up-13-september-2026) separates current identities/results from the original PR #25 checkpoint.
- Eight actual-component regressions/30 subtests passed under the unchanged offline deny harness: warning/missing-output deficiencies, correlated cleanup, no-closure and no-terminal-proof conservative paths, VALID/FAIL and existing generic BLOCKED support, unknown/malformed rejection and fresh-assessment disagreement. Actual scientific assessment was not mocked into INCONCLUSIVE; native abort coverage was not broadened.
- Complete frozen-source validation passed 369 integration tests/577 subtests and 153 B0/Adapter tests/175 subtests, with zero failures/errors/skips/collection errors or forbidden-access attempts and unchanged hashes. Focused/projection subsets are included, not added again. Compilation of 29 Python files, all eleven scientific dependency hashes, whitespace and document links passed; the 56,943,083-byte full synthetic selection passed the unchanged writer bound and readback/finalization.
- Prepared one normal follow-up commit/push on the existing PR #25 branch under the unchanged installed privacy guard. No native revalidation, P2 retry, simulator, calibration, AWS/private Candidate or routing activity occurred. No selected concentration, dissertation delta or readiness claim is introduced. Next gate: `REVIEW_PR25_INCONCLUSIVE_HANDOFF_CORRECTION_BEFORE_MERGE`; not executed here, and PR #25 remains draft/unmerged.

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
