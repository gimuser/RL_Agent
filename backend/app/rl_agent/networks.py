import torch
import torch.nn as nn


class QNetwork(nn.Module):
    """
    Deep Q-Network (DQN)
    """

    def __init__(self, state_size: int, action_size: int):
        super().__init__()

        self.model = nn.Sequential(
            nn.Linear(state_size, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, action_size)
        )

    def forward(self, x):
        return self.model(x)


class ActorNetwork(nn.Module):
    """
    PPO Actor Network
    """

    def __init__(self, state_size: int, action_size: int):
        super().__init__()

        self.model = nn.Sequential(
            nn.Linear(state_size, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, action_size),
            nn.Softmax(dim=-1)
        )

    def forward(self, x):
        return self.model(x)


class CriticNetwork(nn.Module):
    """
    PPO Critic Network
    """

    def __init__(self, state_size: int):
        super().__init__()

        self.model = nn.Sequential(
            nn.Linear(state_size, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 1)
        )

    def forward(self, x):
        return self.model(x)