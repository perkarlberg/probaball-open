"""Blend-mechanics backtest: rank-ladder vs magnitude-preserving, on real matches.

The live model turns each signal (Elo, FIFA, odds, expert) into a *rank*, maps
that rank onto the FIFA-points ladder, and blends — throwing away every signal's
magnitude. We can't backtest the odds/expert legs (no history), but we CAN
backtest the *combining mechanism* on the two strength signals that do have a
past: walk-forward **Elo** and point-in-time **FIFA ranking**.

A 2x3 grid (signals x representation), match model held fixed:

                 rank-ladder      log-odds          goal-space
  Elo + FIFA        A                B                 C
  Elo only          D                E                 F

  rank-ladder : rank teams in the active pool, map onto the sorted FIFA-points
                ladder, blend 0.85/0.15 (Elo/FIFA). Throws away magnitude. (live)
  log-odds    : standardize each signal (z-score over the pool) and blend
                additively -> geometric / logarithmic opinion pool.
  goal-space  : push each standardized signal through a sigmoid, blend the
                resulting probabilities linearly, map back -> linear opinion
                pool. (For a single signal this is identity, so E == F exactly.)

Match model (fixed across all cells): a team STRENGTH gap -> goal supremacy via a
per-cell OLS  goal_diff ~ a*gap + b*home  (so each representation's arbitrary
units/home-edge are calibrated away; only the *shape* of the representation is
tested), then Dixon-Coles Poisson -> W/D/L, scored by RPS. Lower RPS = better.

  cd backend && python3 -m backtest.blend_grid

Reads the same data folder as the rest of the backtest. No deploy impact.
"""
import bisect
import csv
import math
import os
import random

from .elo import Elo
from .metrics import brier, logloss, rps
from .models import MAXG, score_matrix, wdl_from_lambdas

DATA = os.path.join(os.path.dirname(__file__), "data")
RES = os.path.join(DATA, "results.csv")
FIFA = os.path.join(DATA, "fifa_ranking.csv")
FIT_START, TEST_START, TEST_END = "2010-01-01", "2016-01-01", "2024-09-19"
W_ELO, W_FIFA = 0.85, 0.15      # the live RANK_W
CELLS = ["A", "B", "C", "D", "E", "F"]

# results.csv name -> FIFA ranking name (only the WC-relevant mismatches; the
# rest are non-FIFA / CONIFA sides that legitimately have no ranking -> skipped).
RES_TO_FIFA = {
    "United States": "USA", "South Korea": "Korea Republic",
    "North Korea": "Korea DPR", "Ivory Coast": "Côte d'Ivoire",
    "Iran": "IR Iran", "China": "China PR", "DR Congo": "Congo DR",
    "Cape Verde": "Cabo Verde", "Taiwan": "Chinese Taipei",
    "Kyrgyzstan": "Kyrgyz Republic", "Brunei": "Brunei Darussalam",
}


def sig(x):
    return 1.0 / (1.0 + math.exp(-x)) if x > -30 else 0.0


def logit(p):
    p = min(1 - 1e-9, max(1e-9, p))
    return math.log(p / (1 - p))


def load_fifa():
    """date -> {fifa_name: points}, plus sorted snapshot dates."""
    snaps = {}
    for r in csv.DictReader(open(FIFA, encoding="utf-8")):
        try:
            pts = float(r["total_points"])
        except ValueError:
            continue
        snaps.setdefault(r["date"], {})[r["team"]] = pts
    return snaps, sorted(snaps)


def load_results():
    out = []
    for r in csv.DictReader(open(RES, encoding="utf-8")):
        if r["home_score"] in ("", "NA") or r["away_score"] in ("", "NA"):
            continue
        out.append((r["date"], r["home_team"], r["away_team"],
                    int(r["home_score"]), int(r["away_score"]),
                    r["tournament"], r["neutral"].strip().lower() == "true"))
    out.sort()
    return out


def strength(cell, ze, zf, le, lf):
    """One team's strength under a cell, from its z-scores (ze,zf) and
    ladder-mapped values (le,lf)."""
    if cell == "A":
        return W_ELO * le + W_FIFA * lf
    if cell == "D":
        return le
    if cell == "B":
        return W_ELO * ze + W_FIFA * zf
    if cell == "E" or cell == "F":
        return ze
    if cell == "C":
        return logit(W_ELO * sig(ze) + W_FIFA * sig(zf))


def ols_ab(rows):
    """Fit goal_diff ~ a*gap + b*home (no intercept). rows: (gap, home, gd)."""
    Sgg = Sgh = Shh = Sgd = Shd = 0.0
    for gap, home, gd in rows:
        Sgg += gap * gap; Sgh += gap * home; Shh += home * home
        Sgd += gap * gd;  Shd += home * gd
    det = Sgg * Shh - Sgh * Sgh
    if abs(det) < 1e-12:
        return (Sgd / Sgg if Sgg else 0.0), 0.0
    a = (Shh * Sgd - Sgh * Shd) / det
    b = (Sgg * Shd - Sgh * Sgd) / det
    return a, b


def fit_rho(rows, a, b, base):
    best_nll, best = 1e18, 0.0
    for rho in (x / 100 for x in range(-20, 11)):
        nll = 0.0
        for gap, home, hs, as_ in rows:
            if hs > MAXG or as_ > MAXG:
                continue
            sup = a * gap + b * home
            lh = max(0.05, base / 2 + sup / 2)
            la = max(0.05, base / 2 - sup / 2)
            nll -= math.log(max(1e-12, score_matrix(lh, la, rho)[hs][as_]))
        if nll < best_nll:
            best_nll, best = nll, rho
    return best


def bootstrap_paired(xs, ys, B=5000, seed=20260629):
    """95% CI for mean(xs - ys), paired by match (resample match indices)."""
    rng = random.Random(seed)
    n = len(xs)
    diffs = [x - y for x, y in zip(xs, ys)]
    means = []
    for _ in range(B):
        s = 0.0
        for _ in range(n):
            s += diffs[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    return sum(diffs) / n, means[int(0.025 * B)], means[int(0.975 * B)]


def main():
    snaps, snap_dates = load_fifa()
    matches = load_results()
    fifa_to_res = {v: k for k, v in RES_TO_FIFA.items()}

    elo = Elo()              # home_adv=85 for the walk-forward update (as build_elo)
    seen = set()
    # per cell: fit rows (gap,home,gd) and (gap,home,hs,as); test accumulators
    fit_lin = {c: [] for c in CELLS}
    fit_rho_rows = {c: [] for c in CELLS}
    totals = []
    agg = {c: {"all": [0.0, 0.0, 0.0, 0], "comp": [0.0, 0.0, 0.0, 0]} for c in CELLS}
    permatch = {c: [] for c in CELLS}   # per-match RPS (competitive test), paired
    fitted = None
    n_pool_skip = n_scored = 0

    for date, h, a, hs, as_, tour, neutral in matches:
        if date > TEST_END:
            break
        oi = 0 if hs > as_ else 1 if hs == as_ else 2

        # ---- fit the per-cell goal models once, when test window opens -------
        if date >= TEST_START and fitted is None:
            base = sum(totals) / len(totals)
            fitted = {}
            for c in CELLS:
                a_, b_ = ols_ab(fit_lin[c])
                rho_ = fit_rho(fit_rho_rows[c], a_, b_, base)
                fitted[c] = (a_, b_, base, rho_)
            print(f"fit window {FIT_START}..{TEST_START}: base_goals={base:.2f}, "
                  f"{len(fit_lin['A'])} in-pool fit matches")
            for c in CELLS:
                a_, b_, _, rho_ = fitted[c]
                print(f"  cell {c}: a(scale)={a_:.4f} b(home)={b_:.3f} rho={rho_:.2f}")

        # ---- build the active pool + this match's signals --------------------
        snap = None
        if date >= FIT_START:
            i = bisect.bisect_right(snap_dates, date) - 1
            snap = snaps[snap_dates[i]] if i >= 0 else None

        def fifa_pts(team):
            return snap.get(RES_TO_FIFA.get(team, team)) if snap else None

        ready = snap is not None and h in seen and a in seen
        ph, pa = (fifa_pts(h), fifa_pts(a)) if ready else (None, None)
        if ready and ph is not None and pa is not None:
            # pool = active (already-seen) teams that have a FIFA point now
            pool = []
            for fname, pts in snap.items():
                rname = fifa_to_res.get(fname, fname)
                if rname in seen:
                    pool.append((rname, elo.r[rname], pts))
            if len(pool) >= 20:
                elos = [e for _, e, _ in pool]
                fis = [f for _, _, f in pool]
                me = sum(elos) / len(elos)
                mf = sum(fis) / len(fis)
                se = (sum((e - me) ** 2 for e in elos) / len(elos)) ** 0.5 or 1.0
                sf = (sum((f - mf) ** 2 for f in fis) / len(fis)) ** 0.5 or 1.0
                ladder = sorted(fis, reverse=True)
                elo_rank = {n: i for i, (n, _, _) in
                            enumerate(sorted(pool, key=lambda x: -x[1]))}
                fifa_rank = {n: i for i, (n, _, _) in
                             enumerate(sorted(pool, key=lambda x: -x[2]))}

                def feats(team, pts):
                    ze = (elo.r[team] - me) / se
                    zf = (pts - mf) / sf
                    return ze, zf, ladder[elo_rank[team]], ladder[fifa_rank[team]]

                zeh, zfh, leh, lfh = feats(h, ph)
                zea, zfa, lea, lfa = feats(a, pa)
                home = 0.0 if neutral else 1.0
                comp = "friendly" not in tour.lower()

                for c in CELLS:
                    gap = (strength(c, zeh, zfh, leh, lfh)
                           - strength(c, zea, zfa, lea, lfa))
                    if date >= TEST_START:
                        a_, b_, base_, rho_ = fitted[c]
                        sup = a_ * gap + b_ * home
                        lh = max(0.05, base_ / 2 + sup / 2)
                        la = max(0.05, base_ / 2 - sup / 2)
                        p = wdl_from_lambdas(lh, la, rho_)
                        r = rps(p, oi)
                        for bucket in (["all"] + (["comp"] if comp else [])):
                            acc = agg[c][bucket]
                            acc[0] += r; acc[1] += brier(p, oi)
                            acc[2] += logloss(p, oi); acc[3] += 1
                        if comp:
                            permatch[c].append(r)
                    else:  # fit window
                        fit_lin[c].append((gap, home, hs - as_))
                        fit_rho_rows[c].append((gap, home, hs, as_))
                if date >= FIT_START and date < TEST_START:
                    totals.append(hs + as_)
                if date >= TEST_START:
                    n_scored += 1
            else:
                n_pool_skip += 1

        # ---- always advance Elo on the actual result -------------------------
        elo.update(h, a, hs, as_, tour, neutral)
        seen.add(h); seen.add(a)

    # ---- report --------------------------------------------------------------
    label = {"A": "Elo+FIFA  rank-ladder", "B": "Elo+FIFA  log-odds",
             "C": "Elo+FIFA  goal-space", "D": "Elo-only  rank-ladder",
             "E": "Elo-only  log-odds", "F": "Elo-only  goal-space"}
    print(f"\nTest window {TEST_START}..{TEST_END} — {n_scored} in-pool matches\n" + "=" * 70)
    for bucket, title in (("comp", "COMPETITIVE (no friendlies)"), ("all", "ALL matches")):
        print(f"\n{title}")
        print(f"{'cell':<26}{'RPS':>9}{'Brier':>9}{'logloss':>9}{'n':>7}")
        print("-" * 60)
        base_rps = agg["A"][bucket][0] / max(1, agg["A"][bucket][3])
        for c in CELLS:
            srps, sbr, sll, n = agg[c][bucket]
            if n:
                d = srps / n - base_rps
                print(f"{c+'  '+label[c]:<26}{srps/n:>9.4f}{sbr/n:>9.4f}"
                      f"{sll/n:>9.4f}{n:>7}   {d:+.4f} vs A")
    print("\nLower RPS = better. A = today's live method (rank-ladder).")
    print("Expect E==F (single signal). Key reads: A vs B/C (rank-ladder cost,")
    print("Elo+FIFA), D vs E/F (rank-ladder cost, Elo-only), B/C vs E/F (does FIFA help).")

    print("\nPaired bootstrap on COMPETITIVE matches (5000 resamples, 95% CI):")
    contrasts = [("D", "E", "rank-ladder cost, same Elo signal (cleanest)"),
                 ("A", "E", "today's live method vs clean log-odds Elo"),
                 ("B", "E", "does FIFA add anything (magnitude-preserving)")]
    for x, y, desc in contrasts:
        m, lo, hi = bootstrap_paired(permatch[x], permatch[y])
        sig = "significant" if (lo > 0 or hi < 0) else "NOT significant (CI spans 0)"
        print(f"  {x}-{y}  mean dRPS {m:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]  {sig}")
        print(f"        ({desc})")


if __name__ == "__main__":
    main()
