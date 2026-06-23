"""
Tournament-mode helpers (live World Cup). Bridges fixtures.json (the schedule +
results ledger) and the engine's conditioning:

  * build_cond(fx)        -> {results, outcomes, advanced} fed to engine sims so
                             played matches are fixed and the base 50k simulates
                             only what's left.
  * record_group_result   -> write an actual scoreline into fixtures.json (used
                             by the scrape/martj42 fallback when football-data
                             lags on a score).
  * match_probs / store_preds_for_date -> capture the model's PRE-match W/D/L for
                             each day's games, so they can later be graded.
  * graded_results(fx)    -> predicted-vs-actual for played games (upset = the
                             actual outcome had < UPSET_P pre-match probability).
  * tight_upcoming / scenario_specs -> today's near-coin-flip games and the
                             W/D/L scenario combinations to fan out over.

All team identifiers are the engine's Swedish keys.
"""

import json
import os

import engine

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures.json")
TIGHT_PP = 0.10      # |P(home) - P(away)| <= 10 percentage points = "tight"
MAX_TIGHT = 2        # cap the scenario fan-out at the 2 tightest games
SCENARIO_N = 5000
UPSET_P = 0.25       # actual outcome rated below this pre-match => "upset"


def load_fixtures(path=FIXTURES):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_fixtures(fx, path=FIXTURES):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fx, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------
# Conditioning: played matches -> engine `cond`
# ----------------------------------------------------------------------
def build_cond(fx):
    """Fixed played results for the engine. results: frozenset({a,b}) ->
    {team: goals}; advanced: frozenset -> team that went through (KO shootouts)."""
    results, advanced = {}, {}
    for m in fx.get("group_stage", []):
        res = m.get("result")
        if res:
            results[frozenset((m["home"], m["away"]))] = {
                m["home"]: res["home"], m["away"]: res["away"]}
    for r in fx.get("ko_results", []):
        key = frozenset((r["home_team"], r["away_team"]))
        results[key] = {r["home_team"]: r["home"], r["away_team"]: r["away"]}
        if r.get("winner"):
            advanced[key] = r["winner"]
    return {"results": results, "outcomes": {}, "advanced": advanced}


def enrich_group_matches(fx, group_matches):
    """Annotate the snapshot's per-group match list (engine.group_fixtures order)
    with each match's date, actual result (oriented to the entry's home/away),
    and — for played games — the pre-match verdict (as_predicted / upset). Lets
    the group view show the schedule + results, not just predictions."""
    by_pair = {frozenset((m["home"], m["away"])): m for m in fx["group_stage"]}
    graded = {g["match_no"]: g for g in graded_results(fx)}
    for ms in group_matches.values():
        for e in ms:
            fm = by_pair.get(frozenset((e["home"], e["away"])))
            if not fm:
                continue
            e["date"] = fm["date"]
            res = fm.get("result")
            if res:
                e["result"] = ({"home": res["home"], "away": res["away"]}
                               if fm["home"] == e["home"]
                               else {"home": res["away"], "away": res["home"]})
                g = graded.get(fm["match_no"])
                if g:
                    e["as_predicted"], e["upset"] = g["as_predicted"], g["upset"]


def record_group_result(fx, home_sv, away_sv, hs, as_):
    """Write a scoreline into the matching group fixture (orientation-aware).
    Returns True if a fixture matched."""
    pair = frozenset((home_sv, away_sv))
    for m in fx["group_stage"]:
        if frozenset((m["home"], m["away"])) == pair:
            m["result"] = ({"home": hs, "away": as_} if m["home"] == home_sv
                           else {"home": as_, "away": hs})
            return True
    return False


# ----------------------------------------------------------------------
# Pre-match predictions + grading (predicted-vs-actual)
# ----------------------------------------------------------------------
def match_probs(home_sv, away_sv, p=None, knockout=False):
    """Model pre-match (P(home win), P(draw), P(away win)) for a single match,
    with the appropriate host edge."""
    p = p or engine.DEFAULT_PARAMS
    if knockout:
        ha = p.ko_host_adv if home_sv in engine.HOSTS else 0
        hb = p.ko_host_adv if away_sv in engine.HOSTS else 0
    else:
        ha, hb = engine.home_bonus(home_sv, p), engine.home_bonus(away_sv, p)
    la, lb = engine.expected_lambdas(engine.TEAM_RATING[home_sv],
                                     engine.TEAM_RATING[away_sv], p, ha, hb)
    _, ph, pd, pa = engine._match_outcome(la, lb, p.rho)
    return ph, pd, pa


def store_preds_for_date(fx, date, p=None):
    """Stamp each group match on `date` (not yet stamped) with the model's
    pre-match W/D/L. Called each morning so the day's games carry the prediction
    that was current before kickoff. Returns how many were stamped."""
    n = 0
    for m in fx["group_stage"]:
        if m["date"] == date and "pred" not in m:
            ph, pd, pa = match_probs(m["home"], m["away"], p)
            m["pred"] = {"p_home": round(ph, 4), "p_draw": round(pd, 4),
                         "p_away": round(pa, 4)}
            n += 1
    return n


def graded_results(fx):
    """Predicted-vs-actual for every played group match that carries a stored
    pre-match prediction. Returns rows with the actual outcome, what the model
    rated most likely, the probability it gave the actual outcome, and whether it
    was an upset (actual outcome rated below UPSET_P)."""
    rows = []
    for m in fx["group_stage"]:
        res, pred = m.get("result"), m.get("pred")
        if not res or not pred:
            continue
        hs, as_ = res["home"], res["away"]
        actual = "home" if hs > as_ else ("away" if as_ > hs else "draw")
        probs = {"home": pred["p_home"], "draw": pred["p_draw"], "away": pred["p_away"]}
        predicted = max(probs, key=probs.get)
        rows.append({
            "match_no": m["match_no"], "date": m["date"], "group": m["group"],
            "home": m["home"], "away": m["away"], "hs": hs, "as": as_,
            "actual": actual, "predicted": predicted,
            "p_actual": round(probs[actual], 4),
            "as_predicted": actual == predicted,
            "upset": probs[actual] < UPSET_P,
        })
    return rows


# ----------------------------------------------------------------------
# Forecast evaluation (proper scoring rules + calibration)
# ----------------------------------------------------------------------
CAL_BINS = 10  # reliability-diagram resolution (bin width 0.1)


def evaluation_block(fx):
    """Score the model's PRE-match predictions against the played group games.

    Uses proper scoring rules — RPS (the football standard; Constantinou &
    Fenton 2012) and the multiclass Brier score — plus a reliability/calibration
    curve and observed-vs-expected upset accounting. Computed locally during the
    reseed (the backtest package isn't shipped in the Cloud Run image), so the
    import is function-local. Outcome index is the engine's [home, draw, away].
    """
    from backtest.metrics import rps, brier  # local: not in the Cloud Run image

    played = sorted((m for m in fx["group_stage"] if m.get("result") and m.get("pred")),
                    key=lambda m: (m["date"], m["match_no"]))
    games = []
    sum_rps = sum_brier = 0.0
    n_called = n_upset = 0
    exp_called = exp_upset = 0.0
    cal_pred = [0.0] * CAL_BINS
    cal_obs = [0.0] * CAL_BINS
    cal_n = [0] * CAL_BINS

    for m in played:
        pred = m["pred"]
        probs = [pred["p_home"], pred["p_draw"], pred["p_away"]]
        hs, as_ = m["result"]["home"], m["result"]["away"]
        oi = 0 if hs > as_ else (2 if as_ > hs else 1)
        pi = max(range(3), key=lambda i: probs[i])  # most-likely outcome index
        p_actual = probs[oi]
        sum_rps += rps(probs, oi)
        sum_brier += brier(probs, oi)
        n_called += (pi == oi)
        n_upset += (p_actual < UPSET_P)
        exp_called += max(probs)                          # E[# correct calls]
        exp_upset += sum(p for p in probs if p < UPSET_P)  # E[# upsets]
        for i, p in enumerate(probs):                     # 3 calibration points/game
            b = min(CAL_BINS - 1, int(p * CAL_BINS))
            cal_pred[b] += p
            cal_obs[b] += 1.0 if i == oi else 0.0
            cal_n[b] += 1
        names = ["home", "draw", "away"]
        games.append({
            "match_no": m["match_no"], "date": m["date"], "group": m["group"],
            "home": m["home"], "away": m["away"], "hs": hs, "as": as_,
            "p_home": pred["p_home"], "p_draw": pred["p_draw"], "p_away": pred["p_away"],
            "actual": names[oi], "predicted": names[pi],
            "p_actual": round(p_actual, 4), "rps": round(rps(probs, oi), 4),
            "as_predicted": pi == oi, "upset": p_actual < UPSET_P,
        })

    n = len(games)
    calibration = [{
        "lo": round(b / CAL_BINS, 2), "hi": round((b + 1) / CAL_BINS, 2),
        "mean_pred": round(cal_pred[b] / cal_n[b], 4) if cal_n[b] else None,
        "obs": round(cal_obs[b] / cal_n[b], 4) if cal_n[b] else None,
        "n": cal_n[b],
    } for b in range(CAL_BINS)]
    # Is the run more/less eventful than the model expected? Compare observed
    # upsets to their expected count, with a ±1-game dead band for the small N.
    diff = n_upset - exp_upset
    verdict = "inline" if abs(diff) <= 1.0 else ("more" if diff > 0 else "fewer")

    return {
        "n": n,
        "mean_rps": round(sum_rps / n, 4) if n else None,
        "mean_brier": round(sum_brier / n, 4) if n else None,
        "n_called": n_called, "called_expected": round(exp_called, 2),
        "n_upset": n_upset, "upset_expected": round(exp_upset, 2),
        "upset_verdict": verdict,
        "upset_p": UPSET_P,
        "calibration": calibration,
        "games": games,
    }


# ----------------------------------------------------------------------
# Tight upcoming games + scenario fan-out
# ----------------------------------------------------------------------
def _played_pairs(fx):
    pairs = {frozenset((m["home"], m["away"])) for m in fx["group_stage"] if m.get("result")}
    pairs |= {frozenset((r["home_team"], r["away_team"])) for r in fx.get("ko_results", [])}
    return pairs


def tight_upcoming(fx, date, p=None):
    """Group matches on `date` that are not yet played and are near coin-flips
    (|P(home) - P(away)| <= TIGHT_PP), the MAX_TIGHT tightest first. Each row
    carries the three W/D/L probabilities."""
    played = _played_pairs(fx)
    out = []
    for m in fx["group_stage"]:
        if m["date"] != date or m.get("result"):
            continue
        if frozenset((m["home"], m["away"])) in played:
            continue
        ph, pd, pa = match_probs(m["home"], m["away"], p)
        if abs(ph - pa) <= TIGHT_PP:
            out.append({"match_no": m["match_no"], "home": m["home"], "away": m["away"],
                        "p_home": ph, "p_draw": pd, "p_away": pa, "spread": abs(ph - pa)})
    out.sort(key=lambda r: r["spread"])
    return out[:MAX_TIGHT]


def scenario_specs(tight):
    """Cartesian product of W/D/L outcomes over the tight games. Each scenario is
    a list of {match_no, home, away, outcome ('home'|'draw'|'away'), label,
    prob, force} where `force` is the engine outcome spec (winning team or
    'draw') and `prob` is the model's pre-match probability of that outcome."""
    import itertools
    if not tight:
        return []
    per = []
    for t in tight:
        opts = [
            ("home", t["home"], t["p_home"]),
            ("draw", "draw", t["p_draw"]),
            ("away", t["away"], t["p_away"]),
        ]
        per.append([(t, oc, force, pr) for (oc, force, pr) in opts])
    scenarios = []
    for combo in itertools.product(*per):
        legs, prob = [], 1.0
        for (t, oc, force, pr) in combo:
            res = (f"{t['home']} beats {t['away']}" if oc == "home"
                   else f"{t['away']} beats {t['home']}" if oc == "away"
                   else f"{t['home']}–{t['away']} draw")
            legs.append({"match_no": t["match_no"], "home": t["home"],
                         "away": t["away"], "outcome": oc, "force": force, "label": res})
            prob *= pr
        scenarios.append({"legs": legs, "prob": round(prob, 4)})
    return scenarios
