class Evaluator:
    """
    Evaluate the performance of a Reinforcement Learning agent.
    """

    def __init__(self):
        self.rewards = []

    def add_reward(self, reward):
        """
        Store a reward from one episode.
        """
        self.rewards.append(reward)

    def average_reward(self):
        """
        Compute the average reward.
        """
        if len(self.rewards) == 0:
            return 0.0

        return sum(self.rewards) / len(self.rewards)

    def total_reward(self):
        """
        Compute the cumulative reward.
        """
        return sum(self.rewards)

    def reset(self):
        """
        Clear all stored rewards.
        """
        self.rewards.clear()


if __name__ == "__main__":

    evaluator = Evaluator()

    evaluator.add_reward(10)
    evaluator.add_reward(15)
    evaluator.add_reward(20)

    print("Average Reward :", evaluator.average_reward())
    print("Total Reward   :", evaluator.total_reward())