"""Odds leg: convert bookmaker title odds -> a log-strength on the Elo scale.

Exploratory (informs the blended_ratings rewrite; not wired into the live model
yet). Three pieces:

1. DE-VIG. Current model uses multiplicative normalization (avg implied prob /
   booksum), which ignores favourite-longshot bias and understates favourites in
   a long-tailed title market. Compare against Shin's method (research pick).

2. COMPRESSION. Title probability is a steeply convex function of strength: a
   small per-match edge compounds over the knockout rounds. We measure the
   amplification k empirically (Monte-Carlo single-elim over the real strength
   spread): logit(title%) ~= k * (log-strength). To invert title odds back to a
   strength we DE-compress: strength ~= logit(title%) / k. (This is the "Lite+"
   conversion; full bracket-inversion would also strip the draw/path effect.)

3. COMPARE. Put the market-implied log-strength next to Elo's, on one scale, to
   see where the market and our rating actually disagree.

  cd backend && python3 -m fitting.odds_to_strength
"""
import math
import random

import model_data as md

R173 = 400.0 / math.log(10)   # 173.7: Elo points per natural log-odds unit


def raw_probs():
    """Averaged raw implied title prob per team (SV keys), pre-normalisation."""
    raw = {}
    for team_en, bybook in md.BOOKMAKER_ODDS.items():
        sv = md.to_sv(team_en)
        if sv and bybook:
            ps = [md.american_to_prob(o) for o in bybook.values()]
            raw[sv] = sum(ps) / len(ps)
    return raw


def devig_mult(raw):
    tot = sum(raw.values())
    return {t: p / tot for t, p in raw.items()}


def devig_shin(raw):
    """Shin (1992): solve z so the implied probs sum to 1; corrects FLB."""
    teams = list(raw)
    r = [raw[t] for t in teams]
    V = sum(r)

    def p_of(z):
        return [(math.sqrt(z * z + 4 * (1 - z) * ri * ri / V) - z) / (2 * (1 - z))
                for ri in r]
    lo, hi = 0.0, 0.95
    for _ in range(80):
        mid = (lo + hi) / 2
        if sum(p_of(mid)) > 1:   # sum decreases as z rises
            lo = mid
        else:
            hi = mid
    z = (lo + hi) / 2
    return dict(zip(teams, p_of(z))), z


def measure_compression(strengths, sims=40000, seed=20260629):
    """k = slope of logit(title%) on log-strength, from a single-elim MC over a
    field of size 2^r. strengths: centred natural-log-odds. Returns (k, champ%)."""
    rng = random.Random(seed)
    n = len(strengths)
    wins = [0] * n
    for _ in range(sims):
        alive = list(range(n))
        rng.shuffle(alive)
        while len(alive) > 1:
            nxt = []
            for i in range(0, len(alive), 2):
                a, b = alive[i], alive[i + 1]
                pa = 1.0 / (1.0 + math.exp(-(strengths[a] - strengths[b])))
                nxt.append(a if rng.random() < pa else b)
            alive = nxt
        wins[alive[0]] += 1
    p = [w / sims for w in wins]
    xs, ys = [], []
    for s, pi in zip(strengths, p):
        if pi > 0:
            xs.append(s); ys.append(math.log(pi / (1 - pi)))
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    k = (sum((x - mx) * (y - my) for x, y in zip(xs, ys))
         / sum((x - mx) ** 2 for x in xs))
    return k, p


def main():
    elo = md.ELO_RATING
    raw = raw_probs()
    mult = devig_mult(raw)
    shin, z = devig_shin(raw)

    print(f"overround (booksum) = {sum(raw.values()):.3f}   Shin z = {z:.3f}\n")
    print("de-vig comparison (top 8 by market):")
    print(f"{'team':<14}{'mult%':>8}{'Shin%':>8}{'shift':>8}")
    for t, _ in sorted(shin.items(), key=lambda x: -x[1])[:8]:
        print(f"{t:<14}{mult[t]*100:>8.1f}{shin[t]*100:>8.2f}{(shin[t]-mult[t])*100:>+8.2f}")
    print("(Shin shifts probability toward favourites, away from the longshot tail.)\n")

    # measure compression on the 32 strongest WC teams (5 KO rounds = current
    # R32 depth), strengths = Elo on the natural log-odds scale, centred.
    top = sorted(elo, key=lambda t: -elo[t])[:32]
    me = sum(elo[t] for t in top) / len(top)
    s = [(elo[t] - me) / R173 for t in top]
    k, champ = measure_compression(s)
    print(f"measured compression k = {k:.2f}  (logit(title%) per unit log-strength)")
    print(f"  -> a 1.0 log-odds match edge becomes ~{k:.1f} log-odds at the title.")
    print(f"  -> de-compression: implied strength = logit(title%) / {k:.2f}\n")

    # convert market (Shin) title odds -> implied log-strength, compare to Elo
    teams = [t for t in top if shin.get(t, 0) > 0]
    lo = {t: math.log(shin[t] / (1 - shin[t])) for t in teams}
    ml = sum(lo.values()) / len(lo)
    mkt_s = {t: (lo[t] - ml) / k for t in teams}          # market-implied, centred
    elo_s = {t: (elo[t] - me) / R173 for t in teams}       # Elo, centred
    print("market-implied log-strength vs Elo log-strength (centred, top 16):")
    print(f"{'team':<14}{'Elo s':>9}{'mkt s':>9}{'diff':>8}")
    for t in sorted(teams, key=lambda t: -elo_s[t])[:16]:
        d = mkt_s[t] - elo_s[t]
        flag = "  market higher" if d > 0.15 else ("  Elo higher" if d < -0.15 else "")
        print(f"{t:<14}{elo_s[t]:>+9.2f}{mkt_s[t]:>+9.2f}{d:>+8.2f}{flag}")
    print("\nRecipe (Lite+): Shin de-vig -> logit -> divide by measured k -> log-strength,")
    print("then log-pool with Elo. Open: log vs linear pool (decide vs live grading).")


if __name__ == "__main__":
    main()
