"""Scoring metrics for probabilistic match forecasts.

Outcome convention: ordered [home win, draw, away win]; outcome index 0/1/2.
"""
import math


def rps(probs, outcome):
    """Ranked Probability Score for ordered outcomes (0 = perfect, 1 = worst).

    Penalises confident wrong predictions and rewards calibration; the standard
    metric for ordered match outcomes. probs = [p_home, p_draw, p_away].
    """
    n = len(probs)
    cum_p = cum_o = total = 0.0
    for i in range(n - 1):
        cum_p += probs[i]
        cum_o += 1.0 if i == outcome else 0.0
        total += (cum_p - cum_o) ** 2
    return total / (n - 1)


def brier(probs, outcome):
    """Multiclass Brier score (0 = perfect, 2 = worst)."""
    return sum((p - (1.0 if i == outcome else 0.0)) ** 2 for i, p in enumerate(probs))


def logloss(probs, outcome, eps=1e-12):
    """Negative log-likelihood of the realised outcome."""
    return -math.log(max(eps, probs[outcome]))
