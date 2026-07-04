"""Minimal fixture model: one level, one inflow rate, one parameter,
one auxiliary, plus deliberate extractor blind-spot material."""

import numpy as np

GAMMA = 0.3


def step(state, demand, delay):
    pressure = np.tanh(demand)          # aux <- demand (np dropped)
    inflow = GAMMA * pressure           # rate <- param, aux
    outflow = state.stock / delay       # rate <- level (attribute prefix)
    state.stock += inflow - outflow     # level <- rates (AugAssign)
    report: float = inflow + outflow    # AnnAssign
    return report


def hidden_dependency(demand, delay):
    # Blind spot: dependencies inside a bare return are not extracted.
    return demand / delay
