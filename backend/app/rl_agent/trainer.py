from .dqn import DQNAgent
from .ppo import PPOAgent
from .checkpoint import CheckpointManager
class Trainer:
    """
    Reinforcement Learning Trainer
    """

    def __init__(
        self,
        algorithm="dqn",
        state_dim=4,
        action_dim=2,
    ):

        self.algorithm = algorithm.lower()

        if self.algorithm == "dqn":
            self.agent = DQNAgent(
                state_dim=state_dim,
                action_dim=action_dim,
            )

        elif self.algorithm == "ppo":
            self.agent = PPOAgent(
                state_dim=state_dim,
                action_dim=action_dim,
            )

        else:
            raise ValueError("Unsupported algorithm")

        self.checkpoint = CheckpointManager()

    def train(self, episodes=10):

        print(f"Training using {self.algorithm.upper()}")

        for episode in range(episodes):

            print(f"Episode {episode + 1}/{episodes}")

            # هنا مستقبلاً غادي يجي Environment
            # state = env.reset()
            # while not done:
            #     action = self.agent.act(state)
            #     next_state, reward, done = env.step(action)
            #     ...

            if hasattr(self.agent, "update"):
                self.agent.update()

            if (episode + 1) % 5 == 0:

                if hasattr(self.agent, "model"):

                    self.checkpoint.save(
                        self.agent.model,
                        self.agent.optimizer,
                        episode + 1,
                    )

        print("Training completed.")


if __name__ == "__main__":

    trainer = Trainer(
        algorithm="dqn",
        state_dim=4,
        action_dim=2,
    )

    trainer.train(episodes=10)
class TrainingMetrics:
    def __init__(self):
        self.rewards = []
        self.losses = []
        self.epsilons = []

    def add(self, reward, loss=None, epsilon=None):
        self.rewards.append(reward)
        if loss is not None:
            self.losses.append(loss)
        if epsilon is not None:
            self.epsilons.append(epsilon)