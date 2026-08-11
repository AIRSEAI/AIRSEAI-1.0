import torch
import torch.nn.functional as F


def selective_scan_ref(x, dt, A, B, C, D, z=None, dt_bias=None, initial_state=None):
    # Compact pure-PyTorch semantic reference for the Mamba-v1 recurrence.
    assert x.ndim == 3
    bsz, seqlen, d_inner = x.shape
    d_state = A.shape[-1]

    if initial_state is None:
        state = torch.zeros(
            bsz, d_inner, d_state, dtype=x.dtype, device=x.device
        )
    else:
        state = initial_state.to(device=x.device, dtype=x.dtype).clone()

    ys = []
    for t in range(seqlen):
        dt_t = dt[:, t, :]
        if dt_bias is not None:
            dt_t = dt_t + dt_bias
        dt_t = F.softplus(dt_t)

        dA = torch.exp(torch.einsum("bd,dn->bdn", dt_t, A))
        dB = torch.einsum("bd,bn->bdn", dt_t, B[:, t, :])

        x_t = x[:, t, :]
        state = state * dA + x_t.unsqueeze(-1) * dB

        y_t = torch.einsum("bdn,bn->bd", state, C[:, t, :])
        y_t = y_t + D * x_t
        if z is not None:
            y_t = y_t * F.silu(z[:, t, :])
        ys.append(y_t)

    return torch.stack(ys, dim=1), state


def make_cpu_scan_inputs(seed=7, dtype=torch.float32):
    g = torch.Generator(device="cpu")
    g.manual_seed(seed)

    batch = 2
    length = 8
    d_inner = 32
    d_state = 8

    x = 0.25 * torch.randn(batch, length, d_inner, generator=g, dtype=dtype)
    dt = -2.0 + 0.25 * torch.randn(batch, length, d_inner, generator=g, dtype=dtype)
    A = -torch.exp(
        torch.linspace(0.0, 1.0, d_state, dtype=dtype)
    ).unsqueeze(0).repeat(d_inner, 1)
    B = 0.2 * torch.randn(batch, length, d_state, generator=g, dtype=dtype)
    C = 0.2 * torch.randn(batch, length, d_state, generator=g, dtype=dtype)
    D = torch.ones(d_inner, dtype=dtype)
    z = 0.25 * torch.randn(batch, length, d_inner, generator=g, dtype=dtype)
    dt_bias = 0.05 * torch.randn(d_inner, generator=g, dtype=dtype)

    return x, dt, A, B, C, D, z, dt_bias


def to_device(items, device):
    return tuple(t.to(device) for t in items)
