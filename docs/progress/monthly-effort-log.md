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
