# Sutton and Barto: Chapter 1 Learning Note

**Status:** In progress — I had reached Section 1.5 by 28 July 2026.

## What I understand so far

Chapter 1 is helping me see reinforcement learning as learning how to act through interaction, rather than learning a correct answer from labelled examples. The agent chooses an action, observes its consequences through the next situation and reward, and gradually improves its behaviour. This makes traffic-signal control a natural RL problem: changing a signal affects not only the vehicles waiting now, but also queues and congestion later in the network.

The agent-environment boundary is especially important. In Shreya's setting, the controller is the agent. SUMO, the road network, vehicle arrivals, routes, and traffic dynamics form the environment. The controller observes a simplified traffic state and chooses a signal phase, but it does not directly control how individual vehicles accelerate, change lanes, or enter the network.

I currently understand the four main elements as follows. A **policy** describes how the controller chooses a phase from the observed traffic state. The **reward** gives immediate feedback about congestion. A **value function** looks beyond that immediate reward and estimates the longer-term desirability of a state or action. A **model**, when available to the learner, predicts what the environment will do next. The algorithms in the paper are model-free even though SUMO itself is a simulator of the environment.

The distinction between reward and value is becoming clearer to me. Giving green to the longest queue may produce the best immediate reward, yet it could starve another approach or push traffic into an already congested downstream junction. Value is meant to capture these delayed consequences. This is also why the problem cannot be reduced to choosing whichever lane currently has the largest queue.

Section 1.5 uses tic-tac-toe to make several ideas concrete: values can be learned from experience, a greedy action uses current knowledge, and occasional exploratory actions create information that may improve later decisions. For traffic control, exploration cannot mean trying arbitrary unsafe phases. It has to operate within the set of valid signal plans and, in a dissertation experiment, should first take place in simulation.

## Mapping Chapter 1 to the traffic problem

My present mapping is deliberately provisional and will be refined as I study the formal MDP chapters.

| RL idea | Current traffic-control interpretation |
|---|---|
| Agent | The signal-control policy; in a multi-agent view, each controlled junction may be an agent. |
| Environment | SUMO, vehicle demand and routes, the road network, and traffic dynamics. |
| State or observation | Aggregated queue length and elapsed waiting-time features at the junctions. |
| Action | Selection of one valid green-phase pattern at each controlled junction. |
| Reward | Negative congestion cost based on queue length and elapsed waiting. |
| Policy | The rule or learned distribution that maps traffic observations to phases. |
| Value function | Expected future discounted congestion reward from a state, or from a state-action pair. |
| Model | A predictor of state transitions and rewards; SUMO simulates these dynamics, although the paper's learner does not model them explicitly. |
| Exploration | Trying non-greedy valid phase choices during training to learn their consequences. |
| Episode | One simulated traffic run, ending when demand is cleared or the time limit is reached. |

## Questions I want to answer without the book open

I will consider the chapter understood when I can explain, in my own words, why a value function differs from a reward signal; where the agent-environment boundary lies in SUMO; and why a locally attractive green phase can be poor over a longer horizon. I should also be able to explain what exploration means for a traffic signal, why it requires safety constraints, and how a simulator can model the environment while the learning algorithm remains model-free.

Before moving on, I will give a five-minute explanation without notes and write a short paragraph on why immediate queue reduction need not maximise discounted return. Any question I cannot answer clearly will be added to the research question bank.

## What comes next

Chapter 2 isolates the exploration-exploitation problem through multi-armed bandits. Chapter 3 introduces finite MDPs and should give me the formal vocabulary needed to state the traffic-control problem precisely. I will keep reading the book, but I will also connect each chapter to the paper and the baseline code so that the theory produces visible research evidence.
