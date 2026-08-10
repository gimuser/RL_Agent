import torch


class InferenceEngine:
    """
    Runs inference using a trained RL model.
    """

    def __init__(self, model):
        self.model = model
        self.model.eval()

    def predict(self, state):
        """
        Predict the best action for a given state.
        """
        with torch.no_grad():
            q_values = self.model(state)
            action = torch.argmax(q_values).item()
        return action