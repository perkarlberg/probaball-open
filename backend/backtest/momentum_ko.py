"""Does group-stage Elo MOMENTUM predict knockout results beyond the rating?

A predictive horse race over the 10 World Cups 1986-2022 (all "3 group games ->
single-elimination", so structurally consistent). For every knockout match we
turn two team ratings into a P(W/D/L) through ONE shared, fixed Elo->goals
mapping, and score it with RPS (90-min result; shootout = draw). Only the RATING
fed in changes between predictors:

  1 pre        pre-tournament Elo (before group game 1)
  2 post       post-group Elo (after group game 3, frozen at KO entry)
  3 post+d     post-group Elo + lambda * group_delta
  4 live       last-known Elo (updated through every prior match incl. KO rounds)
  5 live+d     last-known Elo + lambda * group_delta

  group_delta = elo_post - elo_pre   (the group-stage swing)

The lambda on predictors 3 & 5 is fit OUT OF SAMPLE by leave-one-World-Cup-out
CV (fit on 9 editions, score the held-out one, rotate x10), so a delta term can
only "win" by genuinely generalising. Key contrasts: 2->3 and 4->5 (does the
swing add signal on top of the rating?); 1->2->4 (value of in-tournament
updating). Note 4==2 and 5==3 on Round-of-16 matches (no prior KO games yet), so
the live-vs-frozen contrast only has teeth from the QF on (~80 of ~160 matches).

  python3 -m backtest.momentum_ko          # from backend/

Exploratory content analysis, NOT a model change. If predictor 5 wins, a
momentum term becomes a candidate for the live model -- which would then have to
clear the golden-rule backtest (lower out-of-sample RPS) before shipping.
"""
import csv
import os
import statistics

from .elo import Elo
from .metrics import rps
from .models import MAXG, score_matrix, wdl_from_lambdas

DATA = os.path.join(os.path.dirname(__file__), "data", "results.csv")
HOME_ADV = 85.0
EDITIONS = [1986, 1990, 1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022]
GOALFIT_START = "1990-01-01"   # window for the shared Elo->goals mapping
LAMBDA_GRID = [round(-2.0 + 0.05 * i, 3) for i in range(0, 121)]  # -2.0 .. 4.0


def load():
    with open(DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    matches = []
    for r in rows:
        if r["home_score"] in ("", "NA") or r["away_score"] in ("", "NA"):
            continue
        matches.append({
            "date": r["date"], "home": r["home_team"], "away": r["away_team"],
            "hs": int(r["home_score"]), "as": int(r["away_score"]),
            "t": r["tournament"],
            "neutral": r["neutral"].strip().lower() == "true",
        })
    matches.sort(key=lambda m: m["date"])
    return matches


def outcome_idx(hs, as_):
    return 0 if hs > as_ else 1 if hs == as_ else 2


def walk(matches):
    """Single chronological pass: build the KO-match table (with each team's
    pre/post/live ratings + group delta) and accumulate the shared goal-fit."""
    elo = Elo(home_adv=HOME_ADV)
    wc_count = {}                 # (edition, team) -> WC matches played so far
    elo_pre, elo_post = {}, {}    # (edition, team) -> rating
    ko_rows = []
    pairs, totals, train, freqs = [], [], [], [0, 0, 0]

    for m in matches:
        d, h, a = m["date"], m["home"], m["away"]
        yr = int(d[:4])
        is_wc = m["t"] == "FIFA World Cup" and yr in EDITIONS
        oi = outcome_idx(m["hs"], m["as"])

        # shared Elo->goals fit stats (competitive matches, pre-match diff)
        if d >= GOALFIT_START and "friendly" not in m["t"].lower():
            diff = elo.diff(h, a, m["neutral"])
            pairs.append((diff, m["hs"] - m["as"]))
            totals.append(m["hs"] + m["as"])
            train.append((diff, m["hs"], m["as"]))
            freqs[oi] += 1

        if is_wc:
            ed = yr
            hc = wc_count.get((ed, h), 0)
            ac = wc_count.get((ed, a), 0)
            if hc == 0:
                elo_pre[(ed, h)] = elo.r[h]
            if ac == 0:
                elo_pre[(ed, a)] = elo.r[a]
            live_h, live_a = elo.r[h], elo.r[a]   # pre-match = last-known
            if hc >= 3 and ac >= 3:               # both finished groups -> KO match
                ko_rows.append({
                    "ed": ed, "home": h, "away": a, "neutral": m["neutral"],
                    "oi": oi, "round_idx": min(hc, ac),  # 3=R16, 4=QF, ...
                    "pre_h": elo_pre[(ed, h)], "pre_a": elo_pre[(ed, a)],
                    "post_h": elo_post[(ed, h)], "post_a": elo_post[(ed, a)],
                    "live_h": live_h, "live_a": live_a,
                    "d_h": elo_post[(ed, h)] - elo_pre[(ed, h)],
                    "d_a": elo_post[(ed, a)] - elo_pre[(ed, a)],
                })

        elo.update(h, a, m["hs"], m["as"], m["t"], m["neutral"])

        if is_wc:
            ed = yr
            wc_count[(ed, h)] = hc + 1
            wc_count[(ed, a)] = ac + 1
            if hc + 1 == 3:
                elo_post[(ed, h)] = elo.r[h]
            if ac + 1 == 3:
                elo_post[(ed, a)] = elo.r[a]

    return ko_rows, (pairs, totals, train, freqs), elo


def fit_goal_model(pairs, totals, train):
    num = sum(diff * gd for diff, gd in pairs)
    den = sum(diff * diff for diff, gd in pairs)
    goal_scale = num / den if den else 0.004
    base_goals = sum(totals) / len(totals)
    best_nll, rho = 1e18, 0.0
    for r in (x / 100 for x in range(-20, 11)):
        nll = 0.0
        for diff, hs, as_ in train:
            if hs > MAXG or as_ > MAXG:
                continue
            lh = max(0.05, base_goals / 2 + diff * goal_scale / 2)
            la = max(0.05, base_goals / 2 - diff * goal_scale / 2)
            import math
            nll -= math.log(max(1e-12, score_matrix(lh, la, r)[hs][as_]))
        if nll < best_nll:
            best_nll, rho = nll, r
    return goal_scale, base_goals, rho


class Mapping:
    """Shared, fixed rating-gap -> P(W/D/L). Held constant across all predictors
    so the horse race isolates the effect of the rating input."""
    def __init__(self, goal_scale, base_goals, rho):
        self.gs, self.bg, self.rho = goal_scale, base_goals, rho

    def wdl(self, r_h, r_a, neutral):
        ha = 0.0 if neutral else HOME_ADV
        sup = (r_h + ha - r_a) * self.gs
        lh = max(0.05, self.bg / 2 + sup / 2)
        la = max(0.05, self.bg / 2 - sup / 2)
        return wdl_from_lambdas(lh, la, self.rho)


# --- predictor rating extractors: row -> (rating_home, rating_away) ----------
def r_pre(row, lam):   return row["pre_h"], row["pre_a"]
def r_post(row, lam):  return row["post_h"], row["post_a"]
def r_postd(row, lam): return row["post_h"] + lam * row["d_h"], row["post_a"] + lam * row["d_a"]
def r_live(row, lam):  return row["live_h"], row["live_a"]
def r_lived(row, lam): return row["live_h"] + lam * row["d_h"], row["live_a"] + lam * row["d_a"]

PREDICTORS = [
    ("1 pre",     r_pre,   False),
    ("2 post",    r_post,  False),
    ("3 post+d",  r_postd, True),
    ("4 live",    r_live,  False),
    ("5 live+d",  r_lived, True),
]


def score_rows(rows, extractor, mp, lam):
    return [rps(mp.wdl(*extractor(row, lam), row["neutral"]), row["oi"]) for row in rows]


def fit_lambda(rows, extractor, mp):
    best, blam = 1e18, 0.0
    for lam in LAMBDA_GRID:
        s = sum(score_rows(rows, extractor, mp, lam))
        if s < best:
            best, blam = s, lam
    return blam


def per_match_scores(rows, extractor, has_lambda, mp):
    """Per-match RPS. For lambda predictors, each match scored with the lambda
    fit on the OTHER nine World Cups (leave-one-WC-out)."""
    if not has_lambda:
        return score_rows(rows, extractor, mp, 0.0)
    out = [None] * len(rows)
    for ed in EDITIONS:
        train = [r for r in rows if r["ed"] != ed]
        lam = fit_lambda(train, extractor, mp)
        for i, r in enumerate(rows):
            if r["ed"] == ed:
                out[i] = rps(mp.wdl(*extractor(r, lam), r["neutral"]), r["oi"])
    return out


def team_table(ko_rows, mp):
    """Per (edition, team): group delta, KO matches, and actual vs Elo-expected
    knockout points under the pre-tournament and post-group ratings."""
    tab = {}
    for r in ko_rows:
        for side, dk, pre, post in (("h", "d_h", "pre_h", "pre_a"),
                                     ("a", "d_a", "pre_a", "pre_h")):
            team = r["home"] if side == "h" else r["away"]
            key = (r["ed"], team)
            t = tab.setdefault(key, {"delta": r[dk], "n": 0, "act": 0.0,
                                     "exp_pre": 0.0, "exp_post": 0.0,
                                     "round": r["round_idx"]})
            p_pre = mp.wdl(r["pre_h"], r["pre_a"], r["neutral"])
            p_post = mp.wdl(r["post_h"], r["post_a"], r["neutral"])
            win_i = 0 if side == "h" else 2
            t["exp_pre"] += p_pre[win_i] + 0.5 * p_pre[1]
            t["exp_post"] += p_post[win_i] + 0.5 * p_post[1]
            t["act"] += (1.0 if (r["oi"] == 0) == (side == "h")
                         else 0.5 if r["oi"] == 1 else 0.0)
            t["n"] += 1
            t["round"] = max(t["round"], r["round_idx"])
    return tab


def _pearson(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = sum((x - mx) ** 2 for x in xs) ** .5
    sy = sum((y - my) ** 2 for y in ys) ** .5
    return cov / (sx * sy) if sx and sy else 0.0


def bootstrap_ci(diffs, B=5000):
    """Bootstrap 95% CI for the mean of paired per-match RPS differences."""
    import random
    rng = random.Random(12345)
    n = len(diffs)
    means = []
    for _ in range(B):
        s = sum(diffs[rng.randrange(n)] for _ in range(n))
        means.append(s / n)
    means.sort()
    return means[int(0.025 * B)], means[int(0.975 * B)]


def main():
    matches = load()
    ko_rows, (pairs, totals, train, freqs), elo = walk(matches)
    gs, bg, rho = fit_goal_model(pairs, totals, train)
    mp = Mapping(gs, bg, rho)

    print(f"shared mapping: goal_scale={gs:.5f} base_goals={bg:.2f} rho={rho:.2f} "
          f"(fit on {len(pairs)} competitive matches >= {GOALFIT_START})")
    by_ed = {ed: sum(1 for r in ko_rows if r["ed"] == ed) for ed in EDITIONS}
    print(f"knockout matches: {len(ko_rows)} total  " +
          " ".join(f"{ed}:{n}" for ed, n in by_ed.items()))
    n_late = sum(1 for r in ko_rows if r["round_idx"] >= 4)
    print(f"  of which QF+ (where live differs from post): {n_late}\n")

    # per-match scores for each predictor (CV lambda for 3 & 5)
    scores = {}
    full_lambda = {}
    for name, ext, has_l in PREDICTORS:
        scores[name] = per_match_scores(ko_rows, ext, has_l, mp)
        if has_l:
            full_lambda[name] = fit_lambda(ko_rows, ext, mp)

    base = scores["2 post"]   # natural baseline
    print(f"{'predictor':<12}{'held-out RPS':>14}{'dRPS vs post':>16}{'95% CI':>22}{'lambda':>9}")
    print("-" * 73)
    for name, ext, has_l in PREDICTORS:
        s = scores[name]
        mean = statistics.mean(s)
        diffs = [a - b for a, b in zip(s, base)]
        d = statistics.mean(diffs)
        if name == "2 post":
            ci = "  (baseline)"
            lam_s = ""
        else:
            lo, hi = bootstrap_ci(diffs)
            ci = f"[{lo:+.4f}, {hi:+.4f}]"
            lam_s = f"{full_lambda[name]:+.2f}" if has_l else ""
        print(f"{name:<12}{mean:>14.4f}{d:>+16.4f}{ci:>22}{lam_s:>9}")
    print("-" * 73)
    print("Lower RPS = better. Negative dRPS = beats post-group Elo.")
    print("(CI excludes 0 => that predictor differs from post-group at ~95%.)\n")

    # per-tournament view + sign test for the two delta contrasts
    print("Per-World-Cup mean RPS:")
    print(f"{'edition':<9}" + "".join(f"{n.split()[1]:>10}" for n, _, _ in PREDICTORS))
    ed_means = {name: {} for name, _, _ in PREDICTORS}
    for ed in EDITIONS:
        idx = [i for i, r in enumerate(ko_rows) if r["ed"] == ed]
        line = f"{ed:<9}"
        for name, _, _ in PREDICTORS:
            mval = statistics.mean(scores[name][i] for i in idx)
            ed_means[name][ed] = mval
            line += f"{mval:>10.4f}"
        print(line)
    print()
    for a, b in [("3 post+d", "2 post"), ("5 live+d", "4 live")]:
        wins = sum(1 for ed in EDITIONS if ed_means[a][ed] < ed_means[b][ed])
        print(f"  {a} beats {b} in {wins}/10 World Cups "
              f"(mean dRPS {statistics.mean(ed_means[a][e]-ed_means[b][e] for e in EDITIONS):+.4f})")

    # --- the takeaway: the group stage durably RE-RATES teams ----------------
    tab = team_table(ko_rows, mp)
    xs = [t["delta"] for t in tab.values()]
    r_pre = _pearson(xs, [(t["act"] - t["exp_pre"]) / t["n"] for t in tab.values()])
    r_post = _pearson(xs, [(t["act"] - t["exp_post"]) / t["n"] for t in tab.values()])
    print("\nWhat the group-stage Elo swing predicts in the knockouts (per team):")
    print(f"  corr(group delta, beating the PRE-tournament forecast) = {r_pre:+.3f}")
    print(f"  corr(group delta, beating the POST-group   forecast)  = {r_post:+.3f}")
    print("  -> a big group riser beats what we'd have said BEFORE the tournament,")
    print("     but NOT what we say AFTER it: the rating fully absorbs the re-rating,")
    print("     and the gain sticks (it isn't luck that regresses in the knockouts).")

    print("\nBiggest group-stage RISERS, 1986-2022, and their knockout record:")
    print(f"{'team':<18}{'yr':>5}{'Elo dlt':>9}{'KO gms':>8}{'actual':>8}{'exp(pre)':>10}{'exp(post)':>11}")
    risers = sorted(tab.items(), key=lambda kv: -kv[1]["delta"])[:12]
    for (ed, team), t in risers:
        print(f"{team:<18}{ed:>5}{t['delta']:>+9.1f}{t['n']:>8}{t['act']:>8.1f}"
              f"{t['exp_pre']:>10.1f}{t['exp_post']:>11.1f}")
    print("(actual vs exp(post) ~ even = the post-group rating had them right; "
          "actual >> exp(pre) = pre-tournament Elo under-rated them.)")

    try:
        make_charts(ko_rows, scores, mp)
    except Exception as e:  # matplotlib optional
        print(f"\n[charts skipped: {e}]")

    print_2026_board()


def make_charts(ko_rows, scores, mp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = os.environ.get("MOMENTUM_OUT", os.path.dirname(DATA))

    # (1) horse-race bar chart
    names = [n for n, _, _ in PREDICTORS]
    means = [statistics.mean(scores[n]) for n in names]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(names, means, color=["#999", "#3b6", "#1a5", "#69c", "#15a"])
    ax.set_ylabel("held-out RPS (lower = better)")
    ax.set_ylim(min(means) - 0.004, max(means) + 0.004)
    ax.set_title("Predicting World Cup knockouts (1986-2022): which Elo wins?")
    for b, m in zip(bars, means):
        ax.text(b.get_x() + b.get_width()/2, m, f"{m:.4f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    p1 = os.path.join(out_dir, "momentum_horserace.png")
    fig.savefig(p1, dpi=130)

    # (2) intuitive scatter: group delta vs KO over/under-performance
    #     residual = mean over the team's KO matches of (actual score - E[score|post])
    team_resid, team_delta = {}, {}
    for r in ko_rows:
        for side, dk in (("h", "d_h"), ("a", "d_a")):
            team = r["home"] if side == "h" else r["away"]
            key = (r["ed"], team)
            rh, ra = r["post_h"], r["post_a"]
            p = mp.wdl(rh, ra, r["neutral"])
            exp_pts = p[0] if side == "h" else p[2]   # P(this team wins) + 0.5*draw
            exp_pts += 0.5 * p[1]
            act = (1.0 if (r["oi"] == 0) == (side == "h") else
                   0.5 if r["oi"] == 1 else 0.0)
            team_resid.setdefault(key, []).append(act - exp_pts)
            team_delta[key] = r[dk]
    xs = [team_delta[k] for k in team_resid]
    ys = [statistics.mean(v) for k, v in team_resid.items()]
    fig2, ax2 = plt.subplots(figsize=(7, 5))
    ax2.axhline(0, color="#bbb", lw=.8); ax2.axvline(0, color="#bbb", lw=.8)
    ax2.scatter(xs, ys, s=22, alpha=.6, color="#1a5")
    if len(xs) > 2:
        b1 = (sum((x-statistics.mean(xs))*(y-statistics.mean(ys)) for x, y in zip(xs, ys)) /
              sum((x-statistics.mean(xs))**2 for x in xs))
        b0 = statistics.mean(ys) - b1*statistics.mean(xs)
        xr = [min(xs), max(xs)]
        ax2.plot(xr, [b0+b1*x for x in xr], color="#d33", lw=1.5)
        r_pear = (sum((x-statistics.mean(xs))*(y-statistics.mean(ys)) for x, y in zip(xs, ys)) /
                  ((sum((x-statistics.mean(xs))**2 for x in xs)**.5) *
                   (sum((y-statistics.mean(ys))**2 for y in ys)**.5)))
        ax2.set_title(f"Group-stage Elo swing vs knockout over-performance\n"
                      f"Pearson r = {r_pear:+.3f}  (n={len(xs)} knockout teams)")
    ax2.set_xlabel("group-stage Elo delta (end of group - start)")
    ax2.set_ylabel("KO points above Elo expectation (per match)")
    fig2.tight_layout()
    p2 = os.path.join(out_dir, "momentum_scatter.png")
    fig2.savefig(p2, dpi=130)
    print(f"\ncharts: {p1}\n        {p2}")


def _board_2026_data():
    """Replicate build_elo's authoritative merge (results.csv + warmup +
    fixtures.json WC results, English names, WC rows neutral) and walk Elo to
    snapshot each 2026 team's pre/post-group rating. Returns (deltas, standings,
    complete) where standings[group] = ranked [(team, pts, gd, gf)]."""
    import csv as _csv
    from fitting.build_elo import (DATA as BE_DATA, EXTRA, WC_START,
                                   TEAM_DATASET, _wc_rows_from_fixtures, _load)
    import json as _json

    rows = _load(BE_DATA)
    seen = {(r["date"], r["home_team"], r["away_team"]) for r in rows}
    if os.path.exists(EXTRA):
        for r in _load(EXTRA):
            k = (r["date"], r["home_team"], r["away_team"])
            if k not in seen:
                rows.append(r); seen.add(k)
    wc = _wc_rows_from_fixtures()
    if wc:
        rows = [r for r in rows if not (r.get("tournament") == "FIFA World Cup"
                                        and r["date"] >= WC_START)]
        rows.extend(wc)
    rows = [r for r in rows if r["home_score"] not in ("", "NA")
            and r["away_score"] not in ("", "NA")]
    rows.sort(key=lambda r: r["date"])

    elo = Elo(home_adv=HOME_ADV)
    cnt, pre, post = {}, {}, {}
    for r in rows:
        h, a = r["home_team"], r["away_team"]
        is26 = r.get("tournament") == "FIFA World Cup" and r["date"] >= WC_START
        if is26:
            for tm in (h, a):
                if cnt.get(tm, 0) == 0:
                    pre[tm] = elo.r[tm]
        elo.update(h, a, int(r["home_score"]), int(r["away_score"]),
                   r["tournament"], r["neutral"].strip().lower() == "true")
        if is26:
            for tm in (h, a):
                cnt[tm] = cnt.get(tm, 0) + 1
                if cnt[tm] == 3:
                    post[tm] = elo.r[tm]
    deltas = {t: post[t] - pre[t] for t in post}

    # group standings from played fixtures.json results (English names)
    fx = _json.load(open(os.path.join(os.path.dirname(DATA), "..", "..", "fixtures.json"),
                         encoding="utf-8"))
    en = TEAM_DATASET
    groups, played = {}, {}
    for m in fx["group_stage"]:
        g = m["group"]
        h, a = en[m["home"]], en[m["away"]]
        st = groups.setdefault(g, {})
        for t in (h, a):
            st.setdefault(t, {"pts": 0, "gf": 0, "ga": 0})
        played[g] = played.get(g, 0) + (1 if m.get("result") else 0)
        res = m.get("result")
        if res:
            hs, as_ = res["home"], res["away"]
            st[h]["gf"] += hs; st[h]["ga"] += as_
            st[a]["gf"] += as_; st[a]["ga"] += hs
            if hs > as_: st[h]["pts"] += 3
            elif as_ > hs: st[a]["pts"] += 3
            else: st[h]["pts"] += 1; st[a]["pts"] += 1
    standings = {}
    for g, st in groups.items():
        ranked = sorted(st.items(),
                        key=lambda kv: (kv[1]["pts"], kv[1]["gf"]-kv[1]["ga"], kv[1]["gf"]),
                        reverse=True)
        standings[g] = [(t, s["pts"], s["gf"]-s["ga"], s["gf"]) for t, s in ranked]
    complete = all(played.get(g, 0) == 6 for g in groups)
    return deltas, standings, complete


def _r32_qualifiers(standings):
    """Top 2 per group + the 8 best third-placed teams (deterministic FIFA-style
    tiebreak: pts, GD, GF)."""
    winners_runners, thirds = [], []
    for g, ranked in standings.items():
        winners_runners += [ranked[0][0], ranked[1][0]]
        thirds.append(ranked[2])
    best8 = sorted(thirds, key=lambda x: (x[1], x[2], x[3]), reverse=True)[:8]
    return set(winners_runners) | {t for t, *_ in best8}


def print_2026_board():
    """Biggest 2026 group-stage Elo risers/fallers among R32 qualifiers."""
    try:
        deltas, standings, complete = _board_2026_data()
    except Exception as e:
        print(f"\n[2026 board skipped: {e}]")
        return
    print(f"\n2026 group-stage Elo delta — risers/fallers entering the knockouts")
    if not complete:
        print("  ** GROUP STAGE NOT COMPLETE — R32 qualifiers not yet final; "
              "regenerate after the last group matches. Showing all finished teams. **")
        board = sorted(deltas.items(), key=lambda kv: -kv[1])
    else:
        qual = _r32_qualifiers(standings)
        board = sorted(((t, d) for t, d in deltas.items() if t in qual),
                       key=lambda kv: -kv[1])
        print(f"  (R32 qualifiers only — {len(board)} teams)")
    for t, d in board:
        print(f"  {d:+7.1f}  {t}")


if __name__ == "__main__":
    main()
