import os
import torch


class CheckpointManager:
    """
    Manage saving and loading RL model checkpoints
    and the best trained model.
    """

    def __init__(self, checkpoint_dir="models/checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        self.best_model_path = "models/best_model.pth"

        os.makedirs(self.checkpoint_dir, exist_ok=True)
        os.makedirs("models", exist_ok=True)

    def save(
        self,
        model,
        optimizer,
        episode,
        filename="checkpoint.pth",
    ):
        """
        Save a training checkpoint.
        """

        path = os.path.join(
            self.checkpoint_dir,
            filename,
        )

        torch.save(
            {
                "episode": episode,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
            },
            path,
        )

        print(f"Checkpoint saved: {path}")

    def load(
        self,
        model,
        optimizer,
        filename="checkpoint.pth",
    ):
        """
        Load a training checkpoint.
        """

        path = os.path.join(
            self.checkpoint_dir,
            filename,
        )

        if not os.path.exists(path):
            print("No checkpoint found.")
            return 0

        checkpoint = torch.load(path)

        model.load_state_dict(
            checkpoint["model_state_dict"]
        )

        optimizer.load_state_dict(
            checkpoint["optimizer_state_dict"]
        )

        print(f"Checkpoint loaded: {path}")

        return checkpoint["episode"]

    def save_best_model(self, model):
        """
        Save the best performing model.
        """

        torch.save(
            model.state_dict(),
            self.best_model_path,
        )

        print(
            f"Best model saved: {self.best_model_path}"
        )

    def load_best_model(self, model):
        """
        Load the best performing model.
        """

        if not os.path.exists(self.best_model_path):
            print("No best model found.")
            return False

        model.load_state_dict(
            torch.load(self.best_model_path)
        )

        print(
            f"Best model loaded: {self.best_model_path}"
        )

        return True


if __name__ == "__main__":

    from networks import QNetwork
    import torch.optim as optim

    model = QNetwork(10, 4)
    optimizer = optim.Adam(
        model.parameters(),
        lr=0.001,
    )

    manager = CheckpointManager()

    manager.save(
        model,
        optimizer,
        episode=1,
    )

    manager.load(
        model,
        optimizer,
    )

    manager.save_best_model(model)

    manager.load_best_model(model)