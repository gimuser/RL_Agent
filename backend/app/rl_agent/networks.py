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


class DuelingQNetwork(nn.Module):
    """
    Dueling DQN network: separate value and advantage streams.
    """

    def __init__(self, state_size: int, action_size: int):
        super().__init__()
        self.feature = nn.Sequential(
            nn.Linear(state_size, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
        )
        self.value_stream = nn.Sequential(nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))
        self.advantage_stream = nn.Sequential(nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, action_size))

    def forward(self, x):
        features = self.feature(x)
        value = self.value_stream(features)
        adv = self.advantage_stream(features)
        q = value + adv - adv.mean(dim=1, keepdim=True)
        return q


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