#!/usr/bin/env python3
"""
Compute the canonical 50k-tournament snapshot LOCALLY and upload it to the
running Cloud Run service, so the heavy Monte Carlo never runs on Cloud Run.

Usage:  python3 reseed_local.py <API_URL> <ADMIN_TOKEN>

POST /api/refresh accepts an optional precomputed snapshot body; when supplied
the service skips its own simulation and only attaches trend deltas + the baked
analysis.json and writes the result to Firestore. The on-demand 1000-sim user
reruns still run on Cloud Run (they're part of the product) — only this once-a-
day 50k burst moves local.

Keep the constants below in sync with app.py
(CANONICAL_N / CANONICAL_SEED / CANONICAL_PODIUM_TRIES).
"""

import datetime
import json
import os
import random
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # so `engine`/`model_data` resolve regardless of cwd
import engine  # noqa: E402
import tournament as tm  # noqa: E402

CANONICAL_N = int(os.environ.get("CANONICAL_N", "50000"))
CANONICAL_SEED = 42
CANONICAL_PODIUM_TRIES = int(os.environ.get("CANONICAL_PODIUM_TRIES", "60000"))


def _scenario_run(cond, legs, seed):
    """One scenario: base conditioning + forced W/D/L on the tight games."""
    overlay = dict(cond)
    overlay["outcomes"] = {**cond.get("outcomes", {}),
                           **{frozenset((l["home"], l["away"])): l["force"] for l in legs}}
    random.seed(seed)
    r = engine.run_simulation(tm.SCENARIO_N, podium_tries=tm.SCENARIO_N, cond=overlay)
    champ = [{"team": t["team"], "name_en": t.get("name_en"),
              "champion": round(t["champion"], 4)} for t in r["teams"][:8]]
    return champ


def _tournament_block(result, today):
    """Build the tournament-mode extras (predicted-vs-actual, today's tight games
    + scenario fan-out) and attach them to the snapshot. Mutates+saves fixtures
    (stamping today's pre-match predictions). No-op shape pre-tournament."""
    fx = tm.load_fixtures()
    n_pred = tm.store_preds_for_date(fx, today)
    tm.save_fixtures(fx)

    cond = tm.build_cond(fx)
    tm.enrich_group_matches(fx, result.get("group_matches", {}))
    graded = tm.graded_results(fx)
    tight = tm.tight_upcoming(fx, today)
    scenarios = []
    for i, s in enumerate(tm.scenario_specs(tight)):
        scenarios.append({"legs": [{"label": l["label"]} for l in s["legs"]],
                          "prob": s["prob"],
                          "champions": _scenario_run(cond, s["legs"], 100 + i)})

    n_played = sum(1 for m in fx["group_stage"] if m.get("result")) + len(fx.get("ko_results", []))
    result["tournament"] = {
        "as_of": today, "n_played": n_played,
        "graded": graded, "tight": tight, "scenarios": scenarios,
    }
    result["evaluation"] = tm.evaluation_block(fx)
    # Human-readable digest for the summary author.
    print(f"   tournament: {n_played} matches played; stamped {n_pred} preds for {today}")
    ups = [g for g in graded if g["upset"]]
    print(f"   predicted-vs-actual: {len(graded)} graded, {len(ups)} upsets"
          + (": " + ", ".join(f"{g['home']} {g['hs']}-{g['as']} {g['away']}" for g in ups) if ups else ""))
    ev = result["evaluation"]
    if ev["n"]:
        print(f"   evaluation: RPS {ev['mean_rps']} · called {ev['n_called']}/{ev['n']} "
              f"(exp {ev['called_expected']}) · upsets {ev['n_upset']} (exp {ev['upset_expected']}, "
              f"{ev['upset_verdict']})")
    if tight:
        print(f"   tight today: " + "; ".join(f"{t['home']} v {t['away']} "
              f"(H{t['p_home']:.0%}/D{t['p_draw']:.0%}/A{t['p_away']:.0%})" for t in tight))
        for s in scenarios:
            lead = s["champions"][0]
            print(f"     scenario p={s['prob']:.2f} [{' & '.join(l['label'] for l in s['legs'])}]"
                  f" -> {lead['team']} {lead['champion']:.1%}")


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit("usage: reseed_local.py <API_URL> <ADMIN_TOKEN>")
    api_url, token = sys.argv[1].rstrip("/"), sys.argv[2]
    today = datetime.date.today().isoformat()

    t0 = time.time()
    cond = tm.build_cond(tm.load_fixtures())  # played results -> fixed in the sim
    random.seed(CANONICAL_SEED)
    result = engine.run_simulation(CANONICAL_N, podium_tries=CANONICAL_PODIUM_TRIES, cond=cond)
    _tournament_block(result, today)
    body = json.dumps(result).encode()
    print(f"   computed {CANONICAL_N} base sims ({len(cond['results'])} results locked) "
          f"in {time.time() - t0:.0f}s ({len(body) / 1024:.0f} KB); leader {result['teams'][0]['team']}")

    req = urllib.request.Request(
        f"{api_url}/api/refresh", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Admin-Token": token})
    with urllib.request.urlopen(req, timeout=120) as resp:
        print("   server:", resp.read().decode())


if __name__ == "__main__":
    main()
