"""Gradient-based retrieval and orthogonal projection onto matrix-update span."""
import torch
import torch.nn.functional as F

def basis(updates):
    matrix = updates.flatten(1).T
    u, s, _ = torch.linalg.svd(matrix, full_matrices=False)
    keep = s > (s.max() * max(matrix.shape) * torch.finfo(s.dtype).eps)
    return u[:, keep]

def project_residual(gradient, updates):
    q = basis(updates); g = gradient.flatten()
    return (g - q @ (q.T @ g)).reshape_as(gradient)

def gradient(model, x, y, offset=None, loss='mse'):
    w = torch.zeros_like(model.layers[1].weight, requires_grad=True)
    if offset is not None: w = w + offset.detach()
    pred = model(x, w)
    objective = F.mse_loss(pred, y) if loss == 'mse' else F.cross_entropy(pred, y)
    return torch.autograd.grad(objective, w)[0].detach()

def retrieve(g, updates, k=3):
    flat = updates.flatten(1)
    score = (flat @ g.flatten()).abs() / (flat.norm(dim=1) * g.norm() + 1e-12)
    return torch.topk(score, min(k, len(updates))).indices

def features(g, updates):
    r = project_residual(g, updates)
    s = torch.linalg.svdvals(r)
    return torch.tensor([r.norm() / (g.norm() + 1e-12), s[0] / (s.norm()+1e-12), (s[:2]**2).sum() / ((s**2).sum()+1e-12)]).float()
