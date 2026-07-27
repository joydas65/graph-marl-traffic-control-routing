# Initial Mentor Guidance: July 2026

## Technical co-mentor discussion

Shreya confirmed that Joy's dissertation extends her earlier IISc traffic-control research supervised by Prof. Bhatnagar.

### Topics to study

- Deep Q-Networks (DQN)
- actor-critic methods
- graph convolutional networks (GCN)
- SUMO traffic simulation
- TraCI programmatic control

### Recommended first milestone

1. Build the required conceptual foundation.
2. Set up SUMO and TraCI.
3. Obtain the earlier repository.
4. Reproduce the basic model before proposing extensions.

### Practical warnings

- Knowledge acquisition and literature study may require several months.
- Hyperparameter tuning can consume substantial time.
- SUMO experiment runtime must be measured early.
- A meaningful experimental phase may require four to five months.
- Progress should be recorded through regular syncs and weekly or monthly logs.

## Faculty direction already established

- The dissertation should extend the Salmalge-Bhatnagar graph traffic-signal-control work.
- Disruptions such as accidents or temporarily unavailable roads are a directly relevant direction.
- The proposal has been reviewed and accepted as a working direction, but the exact research contribution still requires refinement through evidence and mentor alignment.

## Communication principle

Mentor messages should be brief and decision-oriented. A useful update contains:

1. the question or milestone;
2. the evidence obtained;
3. the student's interpretation;
4. the next proposed action; and
5. one specific decision or clarification requested from the mentor.

Large undifferentiated status messages should be avoided, particularly early in the project.

## Next technical questions for Shreya

- Is this DQN repository an experiment-producing codebase or an earlier prototype?
- Which code and commit produced the 2025 GCQN/GCAC results?
- Which dependency and SUMO versions were used?
- Was the intended state dimension 32 or 80?
- Are missing model, checkpoint, or evaluation files available?
- What reproduction result range should Joy target?
- What reuse and attribution terms should be followed?
