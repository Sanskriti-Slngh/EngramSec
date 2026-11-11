"""Small explicit low-rank updates; all composition is in weight space."""
import torch
from torch import nn
import torch.nn.functional as F

DEVICE = torch.device('cpu')

class MLP(nn.Module):
    def __init__(self, sizes=(32, 64, 64, 8)):
        super().__init__()
        self.layers = nn.ModuleList(nn.Linear(a, b) for a, b in zip(sizes, sizes[1:]))
    def forward(self, x, update=None):
        for i, layer in enumerate(self.layers):
            w = layer.weight if i != 1 or update is None else layer.weight + update
            x = F.linear(x, w, layer.bias)
            if i + 1 < len(self.layers): x = F.relu(x)
        return x

class LowRank(nn.Module):
    def __init__(self, shape, rank):
        super().__init__()
        self.a = nn.Parameter(torch.randn(rank, shape[1]) * 0.03)
        self.b = nn.Parameter(torch.zeros(shape[0], rank))
    def forward(self): return self.b @ self.a

def combine(updates, coefficients):
    return torch.einsum('k,kij->ij', coefficients, updates)

def train_update(model, x, y, rank, steps=200, lr=.03, offset=None, loss='mse'):
    adapter = LowRank(model.layers[1].weight.shape, rank).to(DEVICE)
    optim = torch.optim.Adam(adapter.parameters(), lr=lr)
    offset = torch.zeros_like(model.layers[1].weight) if offset is None else offset.detach()
    for _ in range(steps):
        optim.zero_grad()
        pred = model(x, offset + adapter())
        objective = F.mse_loss(pred, y) if loss == 'mse' else F.cross_entropy(pred, y)
        objective.backward(); optim.step()
    return adapter().detach()

def fit_coefficients(model, x, y, updates, steps=100, lr=.05, loss='mse'):
    c = nn.Parameter(torch.zeros(len(updates)))
    opt = torch.optim.Adam([c], lr=lr)
    for _ in range(steps):
        opt.zero_grad(); pred = model(x, combine(updates, c))
        objective = F.mse_loss(pred, y) if loss == 'mse' else F.cross_entropy(pred, y)
        objective.backward(); opt.step()
    return c.detach()
