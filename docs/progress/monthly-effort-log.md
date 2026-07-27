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

### Decisions

- Maintain one longitudinal research repository rather than a disposable baseline fork plus disconnected dissertation repository.
- Preserve the inherited state with a tag and record every subsequent methodological milestone through focused branches, commits, pull requests, and milestone tags.
- Treat the inherited DQN as Level 0 only; do not claim it reproduces the 2025 graph paper.
- Keep administrative forms, signatures, email screenshots, personal identifiers, credentials, copyrighted papers, and company-confidential material outside the public repository.
- Prioritise reproducibility and controlled research evidence over visible commit volume.

### Current risks and blockers

- The inherited training/testing implementation is not runnable as a trustworthy end-to-end baseline without repair.
- The authoritative GCQN/GCAC code commit and experimental configuration require confirmation from Shreya.
- The upstream repository has no declared licence; reuse and redistribution terms require confirmation.
- Baseline runtime and compute requirements have not yet been measured.
- The central two-timescale coordination mechanism still requires research alignment with Prof. Bhatnagar.

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
