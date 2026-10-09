"""LSTM next-day return model (Architecture.md §15.1)."""

import numpy as np
import torch
from torch import nn


class LSTMForecaster(nn.Module):
    """2 stacked LSTM layers (64 -> 32 units) -> Dropout(0.2) -> Dense(1)."""

    def __init__(
        self, n_features: int, hidden_1: int = 64, hidden_2: int = 32, dropout: float = 0.2
    ):
        super().__init__()
        self.lstm1 = nn.LSTM(n_features, hidden_1, batch_first=True)
        self.lstm2 = nn.LSTM(hidden_1, hidden_2, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(hidden_2, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm1(x)
        out, _ = self.lstm2(out)
        out = self.dropout(out[:, -1, :])
        return self.head(out).squeeze(-1)


def make_sequences(features: np.ndarray, seq_length: int, end_indices: np.ndarray) -> np.ndarray:
    """
    Window ending at (and including) row t, for each t in end_indices:
    features[t - seq_length + 1 : t + 1]. The window only ever looks backwards,
    so it is paired with the target of row t (day t -> t+1) without leakage.
    """
    return np.stack([features[t - seq_length + 1 : t + 1] for t in end_indices]).astype(np.float32)


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)


def train_lstm(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    *,
    epochs: int = 60,
    batch_size: int = 64,
    lr: float = 1e-3,
    patience: int = 8,
    seed: int = 42,
) -> tuple[LSTMForecaster, dict]:
    """Mini-batch Adam on MSE with early stopping on validation loss."""
    set_seed(seed)
    model = LSTMForecaster(n_features=X_train.shape[2])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    Xt, yt = torch.from_numpy(X_train), torch.from_numpy(y_train.astype(np.float32))
    Xv, yv = torch.from_numpy(X_val), torch.from_numpy(y_val.astype(np.float32))
    generator = torch.Generator().manual_seed(seed)

    best_val, best_state, best_epoch, stale = float("inf"), None, 0, 0
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(len(Xt), generator=generator)
        for start in range(0, len(Xt), batch_size):
            idx = order[start : start + batch_size]
            optimizer.zero_grad()
            loss = loss_fn(model(Xt[idx]), yt[idx])
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.no_grad():
            val_loss = loss_fn(model(Xv), yv).item()
        if val_loss < best_val - 1e-6:
            best_val, best_epoch, stale = val_loss, epoch + 1, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return model, {"best_epoch": best_epoch, "best_val_loss": best_val}


def predict(model: LSTMForecaster, X: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return model(torch.from_numpy(X.astype(np.float32))).numpy()
