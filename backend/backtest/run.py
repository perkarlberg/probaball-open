"""
Backtest harness (M1). Walk historical international results chronologically,
maintain walk-forward Elo, fit the Elo->goals mapping on a training window, then
score forecast models on a held-out test window with RPS / Brier / log-loss.

  python3 -m backtest.run            # from backend/

Prints the baseline every later v2 step must beat. No deploy impact.
"""
import csv
import os
import sys

import math

from .elo import Elo
from .metrics import brier, logloss, rps
from .models import MAXG, BaseRate, EloPoisson, score_matrix

DATA = os.path.join(os.path.dirname(__file__), "data", "results.csv")
FIT_START = "2006-01-01"   # accumulate Elo->goals fit stats from here
TEST_START = "2015-01-01"  # score models on matches from here on
TODAY = "2026-05-31"       # ignore unplayed future fixtures


def load():
    with open(DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    matches = []
    for r in rows:
        if r["home_score"] in ("", "NA") or r["away_score"] in ("", "NA"):
            continue
        if r["date"] > TODAY:
            continue
        matches.append({
            "date": r["date"], "home": r["home_team"], "away": r["away_team"],
            "hs": int(r["home_score"]), "as": int(r["away_score"]),
            "t": r["tournament"], "neutral": r["neutral"].strip().lower() == "true",
        })
    matches.sort(key=lambda m: m["date"])
    return matches


def outcome_idx(hs, as_):
    return 0 if hs > as_ else 1 if hs == as_ else 2


def fit_goal_model(pairs, totals, freqs):
    # least-squares slope through origin: goal_diff ~ goal_scale * elo_diff
    num = sum(d * gd for d, gd in pairs)
    den = sum(d * d for d, gd in pairs)
    goal_scale = num / den if den else 0.004
    base_goals = sum(totals) / len(totals)
    n = sum(freqs)
    base_rate = [freqs[0] / n, freqs[1] / n, freqs[2] / n]
    return goal_scale, base_goals, base_rate


def fit_rho(train, gs, bg):
    """Fit the Dixon-Coles low-score parameter by minimising training NLL."""
    best_nll, best_rho = 1e18, 0.0
    for r in (x / 100 for x in range(-20, 11)):
        nll = 0.0
        for diff, hs, as_ in train:
            if hs > MAXG or as_ > MAXG:
                continue
            lh = max(0.05, bg / 2 + diff * gs / 2)
            la = max(0.05, bg / 2 - diff * gs / 2)
            p = score_matrix(lh, la, r)[hs][as_]
            nll -= math.log(max(1e-12, p))
        if nll < best_nll:
            best_nll, best_rho = nll, r
    return best_rho


def main():
    matches = load()
    home_adv = float(os.environ.get("ELO_HOME_ADV", "85"))
    elo = Elo(home_adv=home_adv)
    print(f"[Elo home_adv={home_adv}]")
    pairs, totals, freqs, train = [], [], [0, 0, 0], []
    fitted = None
    # accumulators: per model -> per bucket -> [sum_rps, sum_brier, sum_ll, n]
    buckets = ["all", "competitive", "WC2018", "WC2022"]
    agg = {}

    def add(model_name, bucket, m, p, oi):
        a = agg.setdefault(model_name, {b: [0.0, 0.0, 0.0, 0] for b in buckets})[bucket]
        a[0] += rps(p, oi); a[1] += brier(p, oi); a[2] += logloss(p, oi); a[3] += 1

    models = None
    for m in matches:
        d, oi = m["date"], outcome_idx(m["hs"], m["as"])
        if d >= TEST_START:
            if fitted is None:
                gs, bg, br = fit_goal_model(pairs, totals, freqs)
                rho = fit_rho(train, gs, bg)
                fitted = (gs, bg)
                models = [BaseRate(br),
                          EloPoisson(elo, gs, bg, name="elo_poisson"),
                          EloPoisson(elo, gs, bg, rho=rho, name="elo_dc")]
                print(f"fit: goal_scale={gs:.5f} base_goals={bg:.2f} "
                      f"rho={rho:.2f} base_rate={[round(x, 3) for x in br]}  "
                      f"(train pairs={len(pairs)})")
            comp = "friendly" not in m["t"].lower()
            is_wc = m["t"] == "FIFA World Cup"
            for model in models:
                p = model.predict(m["home"], m["away"], m["neutral"])
                add(model.name, "all", m, p, oi)
                if comp:
                    add(model.name, "competitive", m, p, oi)
                if is_wc and d.startswith("2018"):
                    add(model.name, "WC2018", m, p, oi)
                if is_wc and d.startswith("2022"):
                    add(model.name, "WC2022", m, p, oi)
        elif d >= FIT_START:
            diff = elo.diff(m["home"], m["away"], m["neutral"])
            pairs.append((diff, m["hs"] - m["as"]))
            totals.append(m["hs"] + m["as"])
            train.append((diff, m["hs"], m["as"]))
            freqs[oi] += 1
        # always update Elo (warm-up included)
        elo.update(m["home"], m["away"], m["hs"], m["as"], m["t"], m["neutral"])

    print(f"\nBacktest: matches {TEST_START}..{TODAY}\n" + "=" * 64)
    print(f"{'model':<14}{'bucket':<13}{'RPS':>9}{'Brier':>9}{'logloss':>9}{'n':>7}")
    print("-" * 64)
    for name in agg:
        for b in buckets:
            srps, sbr, sll, n = agg[name][b]
            if n:
                print(f"{name:<14}{b:<13}{srps/n:>9.4f}{sbr/n:>9.4f}{sll/n:>9.4f}{n:>7}")
        print("-" * 64)
    print("Lower RPS = better. elo_poisson should beat base_rate.")


if __name__ == "__main__":
    main()
