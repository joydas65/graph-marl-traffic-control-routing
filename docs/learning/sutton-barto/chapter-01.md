# Sutton and Barto: Chapter 1 Learning Note

- **Status:** In progress
- **Progress recorded:** through Section 1.5 on 28 July 2026
- **Purpose:** Build an explainable foundation, not merely record pages read

## Reference concepts to explain in Joy's own words

These prompts are a study scaffold, not a claim that the material has already been mastered.

- Reinforcement learning studies goal-directed learning through interaction.
- The learner is not given the correct action for every situation; it must evaluate actions through reward and future consequences.
- The agent-environment boundary determines what the learner controls and what it observes.
- Core elements include a policy, reward signal, value function, and optionally a model of the environment.
- Reward evaluates immediate desirability; value estimates longer-term desirability.
- Exploration is necessary because the agent must learn about actions whose consequences are uncertain.
- The Section 1.5 tic-tac-toe example illustrates learning values from experience, self-play, greedy improvement, and occasional exploratory moves.

## Explain-back questions

Joy should answer these without looking at the text:

1. Why is a value function different from the reward signal?
2. In traffic control, what is the agent and what belongs to the environment?
3. What would exploration mean for a traffic signal, and what safety constraint limits it?
4. Why can a locally attractive green phase be globally poor over time?
5. What corresponds to a policy, state, action, reward, and episode in Shreya's experiment?
6. In what sense is SUMO a model of the environment, even if the RL algorithm is model-free?

## Traffic-control mapping exercise

Complete the table in Joy's own words.

| Chapter 1 concept | Traffic-control instance |
|---|---|
| Agent |  |
| Environment |  |
| Observation/state |  |
| Action |  |
| Reward |  |
| Policy |  |
| Value function |  |
| Model |  |
| Exploration |  |
| Episode/continuing task |  |

## Minimum completion evidence

- A five-minute verbal explanation without notes.
- Completed mapping table.
- One paragraph explaining why immediate queue reduction alone may not maximise discounted return.
- One question added to `docs/learning/question-bank.md`.

## Connection to the next reading

Chapter 2 isolates exploration versus exploitation in bandit problems. Chapter 3 then introduces finite MDPs, which provide the formal language needed to express Shreya's traffic-control problem.
