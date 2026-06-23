"""
M6: does FIFA ranking add predictive value beyond Elo, and at what weight?
Walk-forward; for matches where both teams have a FIFA z-score as-of-date, fit
the supremacy as a 2-variable least squares  goal_diff ~ a*elo_diff + b*fifa_zdiff
on the training window, then score Elo-only vs Elo+FIFA on the test window (RPS,
with the same DC rho). The fitted a:b (in standardised units) sets RANK_W.

  cd backend && python3 -m backtest.compare_fifa
"""
from . import fifa
from .elo import Elo
from .metrics import brier, logloss, rps
from .models import wdl_from_lambdas
from .run import FIT_START, TEST_START, TODAY, fit_goal_model, load, outcome_idx

RHO = -0.06


def main():
    matches = load()
    elo = Elo()
    pairs, totals, freqs, train = [], [], [0, 0, 0], []
    tr = []   # (elo_diff, fifa_zdiff, goal_diff)
    te = []   # (elo_diff, fifa_zdiff, oi, comp, wc18, wc22)
    skipped = 0

    for m in matches:
        d, oi = m["date"], outcome_idx(m["hs"], m["as"])
        zd = None
        zh = fifa.zscore(fifa.canon(m["home"]), d)
        za = fifa.zscore(fifa.canon(m["away"]), d)
        if zh is not None and za is not None:
            zd = zh - za
        if d >= TEST_START:
            ediff = elo.diff(m["home"], m["away"], m["neutral"])
            if zd is None:
                skipped += 1
            else:
                te.append((ediff, zd, oi, "friendly" not in m["t"].lower(),
                           m["t"] == "FIFA World Cup" and d[:4] == "2018",
                           m["t"] == "FIFA World Cup" and d[:4] == "2022"))
        elif d >= FIT_START:
            ediff = elo.diff(m["home"], m["away"], m["neutral"])
            pairs.append((ediff, m["hs"] - m["as"]))
            totals.append(m["hs"] + m["as"])
            freqs[oi] += 1
            if zd is not None:
                tr.append((ediff, zd, m["hs"] - m["as"]))
        elo.update(m["home"], m["away"], m["hs"], m["as"], m["t"], m["neutral"])

    gs, bg, _ = fit_goal_model(pairs, totals, freqs)  # elo-only scale

    # 2-var least squares (no intercept): goal_diff ~ a*elo + b*fifa
    sxx = sum(e * e for e, z, g in tr)
    szz = sum(z * z for e, z, g in tr)
    sxz = sum(e * z for e, z, g in tr)
    sxg = sum(e * g for e, z, g in tr)
    szg = sum(z * g for e, z, g in tr)
    det = sxx * szz - sxz * sxz
    a = (szz * sxg - sxz * szg) / det
    b = (sxx * szg - sxz * sxg) / det
    import math
    sd_e = math.sqrt(sxx / len(tr)); sd_z = math.sqrt(szz / len(tr))
    we = abs(a) * sd_e; wf = abs(b) * sd_z
    print(f"goal_scale(elo-only)={gs:.5f}  base={bg:.2f}")
    print(f"2-var fit: a(elo)={a:.5f}  b(fifa_z)={b:.4f}")
    print(f"standardised weight  Elo:{we/(we+wf):.2f}  FIFA:{wf/(we+wf):.2f}")

    def score(use_fifa):
        acc = {k: [0.0, 0.0, 0.0, 0] for k in ("all", "competitive", "WC2018", "WC2022")}
        for ediff, zd, oi, comp, w18, w22 in te:
            sup = (a * ediff + b * zd) if use_fifa else (gs * ediff)
            p = wdl_from_lambdas(max(0.05, bg / 2 + sup / 2),
                                 max(0.05, bg / 2 - sup / 2), RHO)
            for key, on in (("all", True), ("competitive", comp),
                            ("WC2018", w18), ("WC2022", w22)):
                if on:
                    s = acc[key]
                    s[0] += rps(p, oi); s[1] += brier(p, oi); s[2] += logloss(p, oi); s[3] += 1
        return acc

    print(f"\nTest matches with FIFA coverage (skipped {skipped} no-FIFA):")
    print(f"{'model':<12}{'bucket':<13}{'RPS':>9}{'logloss':>9}{'n':>6}")
    print("-" * 49)
    for name, acc in (("elo_only", score(False)), ("elo+fifa", score(True))):
        for b_ in ("all", "competitive", "WC2018", "WC2022"):
            s = acc[b_]
            if s[3]:
                print(f"{name:<12}{b_:<13}{s[0]/s[3]:>9.4f}{s[2]/s[3]:>9.4f}{s[3]:>6}")
        print("-" * 49)


if __name__ == "__main__":
    main()
