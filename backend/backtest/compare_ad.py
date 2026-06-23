"""
M4.2 experiment: does a per-team attack/defence (Maher/Dixon-Coles) model beat
the Elo+DC model on out-of-sample match RPS? Walk-forward; Maher refit yearly on
prior matches (time-decayed); Elo updated continuously. Both use the same DC rho.

  cd backend && python3 -m backtest.compare_ad
"""
import datetime as dt

from . import maher
from .elo import Elo
from .metrics import brier, logloss, rps
from .models import wdl_from_lambdas
from .run import FIT_START, TEST_START, TODAY, fit_goal_model, fit_rho, load, outcome_idx


def ordinal(date_str):
    return dt.date.fromisoformat(date_str).toordinal()


def main():
    matches = load()
    elo = Elo()
    pairs, totals, freqs, train = [], [], [0, 0, 0], []
    gs = bg = rho = None
    # all played matches as (ord, home, away, hg, ag, neutral) for Maher fits
    hist = [(ordinal(m["date"]), m["home"], m["away"], m["hs"], m["as"], m["neutral"])
            for m in matches]

    buckets = ["all", "competitive", "WC2018", "WC2022"]
    models3 = ("elo_dc", "maher_dc", "maher_overall")
    agg = {m: {b: [0.0, 0.0, 0.0, 0] for b in buckets} for m in models3}
    maher_params = None
    maher_overall_params = None
    maher_year = None

    def add(model, b, p, oi):
        a = agg[model][b]
        a[0] += rps(p, oi); a[1] += brier(p, oi); a[2] += logloss(p, oi); a[3] += 1

    for idx, m in enumerate(matches):
        d, oi = m["date"], outcome_idx(m["hs"], m["as"])
        if d >= TEST_START:
            if gs is None:
                gs, bg, br = fit_goal_model(pairs, totals, freqs)
                rho = fit_rho(train, gs, bg)
                print(f"goal fit: scale={gs:.5f} base={bg:.2f} rho={rho:.2f}")
            year = d[:4]
            if year != maher_year:  # refit Maher on everything before this year
                cutoff = ordinal(f"{year}-01-01")
                prior = [h for h in hist if h[0] < cutoff]
                maher_params = maher.fit(prior, cutoff)
                # style-stripped version: same overall (atk/dfn ratio), no style
                # (atk*dfn level set to a common geomean) -> isolates overall.
                atk, dfn, gam = maher_params
                import math as _m
                ts = list(atk)
                c = _m.exp(sum(_m.log(_m.sqrt(atk[t] * dfn[t])) for t in ts) / len(ts))
                a2, d2 = {}, {}
                for t in ts:
                    rt = _m.sqrt(atk[t] / dfn[t])
                    a2[t] = c * rt
                    d2[t] = c / rt
                maher_overall_params = (a2, d2, gam)
                maher_year = year
                print(f"  refit Maher for {year} on {len(prior)} matches")

            comp = "friendly" not in m["t"].lower()
            is_wc = m["t"] == "FIFA World Cup"
            # elo_dc
            sup = elo.diff(m["home"], m["away"], m["neutral"]) * gs
            p_elo = wdl_from_lambdas(max(0.05, bg / 2 + sup / 2),
                                     max(0.05, bg / 2 - sup / 2), rho)
            # maher_dc + style-stripped maher_overall
            lh, la = maher.lambdas(*maher_params, m["home"], m["away"], m["neutral"])
            p_mah = wdl_from_lambdas(max(0.05, lh), max(0.05, la), rho)
            oh, oa = maher.lambdas(*maher_overall_params, m["home"], m["away"], m["neutral"])
            p_ov = wdl_from_lambdas(max(0.05, oh), max(0.05, oa), rho)
            for name, p in (("elo_dc", p_elo), ("maher_dc", p_mah), ("maher_overall", p_ov)):
                add(name, "all", p, oi)
                if comp:
                    add(name, "competitive", p, oi)
                if is_wc and d.startswith("2018"):
                    add(name, "WC2018", p, oi)
                if is_wc and d.startswith("2022"):
                    add(name, "WC2022", p, oi)
        elif d >= FIT_START:
            diff = elo.diff(m["home"], m["away"], m["neutral"])
            pairs.append((diff, m["hs"] - m["as"]))
            totals.append(m["hs"] + m["as"])
            train.append((diff, m["hs"], m["as"]))
            freqs[oi] += 1
        elo.update(m["home"], m["away"], m["hs"], m["as"], m["t"], m["neutral"])

    print(f"\nElo+DC vs Maher+DC ({TEST_START}..{TODAY})\n" + "=" * 56)
    print(f"{'model':<11}{'bucket':<13}{'RPS':>9}{'Brier':>9}{'logloss':>9}{'n':>6}")
    print("-" * 56)
    for name in models3:
        for b in buckets:
            s = agg[name][b]
            if s[3]:
                print(f"{name:<11}{b:<13}{s[0]/s[3]:>9.4f}{s[1]/s[3]:>9.4f}"
                      f"{s[2]/s[3]:>9.4f}{s[3]:>6}")
        print("-" * 56)


if __name__ == "__main__":
    main()
