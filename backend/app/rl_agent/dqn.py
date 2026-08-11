import random
import torch
import torch.nn as nn
import torch.optim as optim

from .networks import QNetwork, DuelingQNetwork
from .memory import ReplayBuffer
from .policy import EpsilonGreedyPolicy


class DQNAgent:
    """
    Deep Q-Network (DQN) Agent.

    This agent interacts with the environment by selecting actions
    using an epsilon-greedy policy. It stores experiences in a replay
    buffer and learns by minimizing the temporal-difference (TD) loss.

    Attributes:
        state_dim (int): Dimension of the input state.
        action_dim (int): Number of possible actions.
        gamma (float): Discount factor.
        epsilon (float): Exploration rate.
        batch_size (int): Number of samples used during training.
    """

    def __init__(
        self,
        state_dim,
        action_dim,
        learning_rate=1e-3,
        gamma=0.99,
        batch_size=64,
        memory_size=10000,
        target_update=100,
        architecture: str = "standard",
        dqn_type: str = "standard",
    ):

        self.device = torch.device("cpu")

        self.state_dim = state_dim
        self.action_dim = action_dim

        self.gamma = gamma
        self.batch_size = batch_size
        self.target_update = target_update
        self.dqn_type = dqn_type  # 'standard' or 'double'

        if architecture == "dueling":
            self.model = DuelingQNetwork(state_dim, action_dim).to(self.device)
            self.target_model = DuelingQNetwork(state_dim, action_dim).to(self.device)
        else:
            self.model = QNetwork(state_dim, action_dim).to(self.device)
            self.target_model = QNetwork(state_dim, action_dim).to(self.device)

        self.target_model.load_state_dict(
            self.model.state_dict()
        )

        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=learning_rate,
        )

        self.criterion = nn.MSELoss()

        self.memory = ReplayBuffer(
            capacity=memory_size
        )

        self.policy = EpsilonGreedyPolicy()

        self.steps = 0

    def act(self, state):
        """
        Select an action for the given state.

        Args:
            state: Current environment state.

        Returns:
            int: Selected action index.
        """

        if not isinstance(state, torch.Tensor):
            state = torch.FloatTensor(state)

        state = state.unsqueeze(0)

        if random.random() < self.policy.epsilon:
            return random.randint(
                0,
                self.action_dim - 1,
            )

        with torch.no_grad():

            q_values = self.model(state)

            return torch.argmax(
                q_values,
                dim=1,
            ).item()

    def remember(
        self,
        state,
        action,
        reward,
        next_state,
        done,
    ):
        """
        Store one transition inside the replay buffer.

        Args:
            state: Current state.
            action: Executed action.
            reward: Received reward.
            next_state: Next environment state.
            done: Episode termination flag.
        """

        self.memory.add(
            state,
            action,
            reward,
            next_state,
            done,
        )

    def update(self):
        """
        Perform one optimization step using a mini-batch sampled
        from the replay buffer.

        Returns:
            float | None:
                Training loss if an update was performed,
                otherwise None.
        """

        if len(self.memory) < self.batch_size:
            return None

        batch = self.memory.sample(self.batch_size)

        states, actions, rewards, next_states, dones = zip(*batch)

        states = torch.FloatTensor(states)
        actions = torch.LongTensor(actions).unsqueeze(1)
        rewards = torch.FloatTensor(rewards).unsqueeze(1)
        next_states = torch.FloatTensor(next_states)
        dones = torch.FloatTensor(dones).unsqueeze(1)

        current_q = self.model(states).gather(1, actions)

        with torch.no_grad():
            if self.dqn_type == "double":
                # Double DQN: action selected by online network, value from target network
                next_actions = self.model(next_states).argmax(dim=1, keepdim=True)
                next_q = self.target_model(next_states).gather(1, next_actions)
            else:
                # Standard DQN: use target network max over actions
                next_q = self.target_model(next_states).max(dim=1, keepdim=True).values
            target_q = rewards + self.gamma * next_q * (1 - dones)

        loss = self.criterion(
            current_q,
            target_q,
        )

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        self.policy.decay()

        self.steps += 1

        if self.steps % self.target_update == 0:
            self.target_model.load_state_dict(
                self.model.state_dict()
            )

        return loss.item()

    def save(self, path):
        """
        Save the trained model.

        Args:
            path (str): Destination file path.
        """

        torch.save(
            self.model.state_dict(),
            path,
        )

    def load(self, path):
        """
        Load a previously trained model.

        Args:
            path (str): Model file path.
        """

        self.model.load_state_dict(
            torch.load(
                path,
                map_location=self.device,
            )
        )

        self.target_model.load_state_dict(
            self.model.state_dict()
        )


if __name__ == "__main__":

    import numpy as np

    agent = DQNAgent(
        state_dim=4,
        action_dim=2,
    )

    state = np.random.rand(4)
    next_state = np.random.rand(4)

    action = agent.act(state)

    agent.remember(
        state,
        action,
        1.0,
        next_state,
        False,
    )

    print("Selected Action:", action)
    print("DQN Agent initialized successfully.")