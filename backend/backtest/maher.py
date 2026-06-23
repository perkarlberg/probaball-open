"""
Maher / Dixon-Coles attack-defence Poisson model, fit by iterative scaling
(closed-form MLE updates, no scipy) with exponential time-decay weighting.

Multiplicative form:
    E[home goals] = gamma * atk[home] * def[away]
    E[away goals] =         atk[away] * def[home]     (no home factor at away)
gamma is the home-advantage multiplier (1.0 at neutral venues). A scale
degeneracy between atk and def is removed by renormalising geomean(atk)=1 each
iteration. Teams unseen in the fit window fall back to league-average (1.0).
"""
import math


def fit(matches, asof_ord, half_life_days=540.0, iters=60):
    """matches: list of (date_ord, home, away, hg, ag, neutral). Returns
    (atk, def_, gamma) dicts/float; weights decay with match age before asof."""
    decay = math.log(2.0) / half_life_days
    teams = set()
    rows = []
    for d, h, a, hg, ag, neutral in matches:
        w = math.exp(-decay * max(0, asof_ord - d))
        rows.append((h, a, hg, ag, neutral, w))
        teams.add(h); teams.add(a)

    atk = {t: 1.0 for t in teams}
    dfn = {t: 1.0 for t in teams}
    gamma = 1.3
    for _ in range(iters):
        # gamma: weighted home goals / weighted (atk_home * def_away) over non-neutral
        gn = gd = 0.0
        for h, a, hg, ag, neutral, w in rows:
            if not neutral:
                gn += w * hg
                gd += w * atk[h] * dfn[a]
        gamma = gn / gd if gd else gamma

        # attack: weighted goals scored / weighted (opp def * venue factor)
        num_a = {t: 0.0 for t in teams}
        den_a = {t: 0.0 for t in teams}
        num_d = {t: 0.0 for t in teams}
        den_d = {t: 0.0 for t in teams}
        for h, a, hg, ag, neutral, w in rows:
            g = gamma if not neutral else 1.0
            num_a[h] += w * hg
            den_a[h] += w * dfn[a] * g
            num_a[a] += w * ag
            den_a[a] += w * dfn[h]
            # defence: goals conceded / (opp atk * venue factor)
            num_d[a] += w * hg          # away team concedes home goals
            den_d[a] += w * atk[h] * g
            num_d[h] += w * ag          # home team concedes away goals
            den_d[h] += w * atk[a]
        for t in teams:
            if den_a[t]:
                atk[t] = max(1e-4, num_a[t] / den_a[t])
            if den_d[t]:
                dfn[t] = max(1e-4, num_d[t] / den_d[t])

        # remove atk/def scale degeneracy: geomean(atk) = 1
        gm = math.exp(sum(math.log(atk[t]) for t in teams) / len(teams))
        if gm > 0:
            for t in teams:
                atk[t] /= gm
                dfn[t] *= gm
    return atk, dfn, gamma


def lambdas(atk, dfn, gamma, home, away, neutral, default=1.0):
    g = 1.0 if neutral else gamma
    ah, dh = atk.get(home, default), dfn.get(home, default)
    aa, da = atk.get(away, default), dfn.get(away, default)
    return g * ah * da, aa * dh
