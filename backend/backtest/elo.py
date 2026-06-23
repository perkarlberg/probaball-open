"""Walk-forward World-Football-style Elo computed from historical results.

Ratings update chronologically, so at any match the *pre-match* ratings use only
prior information — exactly what a backtest needs. Tournament importance scales
the K-factor; goal margin scales it further; home advantage is added unless the
match is at a neutral venue.
"""
from collections import defaultdict

# K-factor by tournament importance (World Football Elo conventions).
def k_factor(tournament: str) -> float:
    t = (tournament or "").lower()
    if "world cup" in t and "qualif" not in t:
        return 60.0
    if "qualif" in t:
        return 40.0
    if any(s in t for s in ("euro", "copa am", "cup of nations", "asian cup",
                            "gold cup", "nations league", "confederations")):
        return 50.0
    if "friendly" in t:
        return 20.0
    return 30.0


class Elo:
    def __init__(self, home_adv: float = 85.0, base: float = 1500.0):
        self.home_adv = home_adv
        self.base = base
        self.r = defaultdict(lambda: base)

    def expected_home(self, home, away, neutral: bool) -> float:
        ha = 0.0 if neutral else self.home_adv
        return 1.0 / (1.0 + 10.0 ** (-(self.r[home] + ha - self.r[away]) / 400.0))

    def diff(self, home, away, neutral: bool) -> float:
        """Pre-match rating difference incl. home advantage (home minus away)."""
        ha = 0.0 if neutral else self.home_adv
        return self.r[home] + ha - self.r[away]

    def update(self, home, away, hs: int, as_: int, tournament: str, neutral: bool):
        exp_h = self.expected_home(home, away, neutral)
        score_h = 1.0 if hs > as_ else 0.5 if hs == as_ else 0.0
        margin = abs(hs - as_)
        g = 1.0 if margin <= 1 else 1.5 if margin == 2 else (11.0 + margin) / 8.0
        delta = k_factor(tournament) * g * (score_h - exp_h)
        self.r[home] += delta
        self.r[away] -= delta
