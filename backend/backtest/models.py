"""Forecast models for the backtest. Each exposes predict(home, away, neutral)
-> [p_home, p_draw, p_away] using only pre-match information."""
import math

MAXG = 10  # truncate the score matrix here


def _poisson_pmf(lam):
    """Return [P(0), P(1), ... P(MAXG)] for a Poisson(lam)."""
    out = []
    p = math.exp(-lam)
    for k in range(MAXG + 1):
        out.append(p)
        p *= lam / (k + 1)
    return out


def _dc_tau(i, j, lh, la, rho):
    """Dixon-Coles low-score dependence factor (1.0 outside the 2x2 corner)."""
    if i == 0 and j == 0:
        return 1.0 - lh * la * rho
    if i == 0 and j == 1:
        return 1.0 + lh * rho
    if i == 1 and j == 0:
        return 1.0 + la * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(lh, la, rho=0.0):
    """DC-adjusted joint score probabilities P[i][j], normalised."""
    ph, pa = _poisson_pmf(lh), _poisson_pmf(la)
    m = [[0.0] * (MAXG + 1) for _ in range(MAXG + 1)]
    s = 0.0
    for i in range(MAXG + 1):
        for j in range(MAXG + 1):
            p = ph[i] * pa[j] * (_dc_tau(i, j, lh, la, rho) if rho else 1.0)
            if p < 0:
                p = 0.0
            m[i][j] = p
            s += p
    if s:
        for i in range(MAXG + 1):
            for j in range(MAXG + 1):
                m[i][j] /= s
    return m


def wdl_from_lambdas(lh, la, rho=0.0):
    """Goal model -> (P home win, P draw, P away win), with optional DC rho."""
    m = score_matrix(lh, la, rho)
    home = draw = away = 0.0
    for i in range(MAXG + 1):
        for j in range(MAXG + 1):
            if i > j:
                home += m[i][j]
            elif i == j:
                draw += m[i][j]
            else:
                away += m[i][j]
    return [home, draw, away]


class BaseRate:
    """Constant home/draw/away frequencies (a naive reference baseline)."""
    name = "base_rate"

    def __init__(self, probs):
        self.probs = probs

    def predict(self, home, away, neutral):
        return self.probs


class EloPoisson:
    """Elo rating gap -> goal supremacy -> independent-Poisson W/D/L.

    The current v1 goal-model shape (supremacy from a rating gap, fixed average
    total goals), but driven by walk-forward Elo so it can be backtested.
    """
    name = "elo_poisson"

    def __init__(self, elo, goal_scale, base_goals, rho=0.0, name=None):
        self.elo = elo
        self.goal_scale = goal_scale
        self.base_goals = base_goals
        self.rho = rho
        if name:
            self.name = name

    def lambdas(self, home, away, neutral):
        sup = self.elo.diff(home, away, neutral) * self.goal_scale
        return (max(0.05, self.base_goals / 2 + sup / 2),
                max(0.05, self.base_goals / 2 - sup / 2))

    def predict(self, home, away, neutral):
        lh, la = self.lambdas(home, away, neutral)
        return wdl_from_lambdas(lh, la, self.rho)
