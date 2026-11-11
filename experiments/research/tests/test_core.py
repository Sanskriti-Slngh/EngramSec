import unittest
import torch
from src.adapters import combine, LowRank
from src.selection import basis, project_residual

class CoreTests(unittest.TestCase):
    def test_combine_full_matrices(self):
        torch.manual_seed(1)
        a = [LowRank((5, 4), 2) for _ in range(2)]
        with torch.no_grad():
            for x in a: x.b.normal_()
        u = torch.stack([x() for x in a]); c = torch.tensor([.3, -.7])
        self.assertTrue(torch.allclose(combine(u,c), .3*u[0]-.7*u[1]))
    def test_projection_with_dependent_vectors(self):
        torch.manual_seed(2)
        u = torch.randn(2, 4, 3); u = torch.cat([u, u[:1]*2])
        r = project_residual(torch.randn(4,3),u)
        self.assertEqual(basis(u).shape[1], 2)
        self.assertLess((u.flatten(1) @ r.flatten()).abs().max().item(), 1e-5)
if __name__ == '__main__': unittest.main()
