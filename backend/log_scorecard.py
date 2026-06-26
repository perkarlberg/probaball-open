#!/usr/bin/env python3
"""
Append a dated snapshot of the model's tournament-stage forecast (+ the current
bookmaker title-implied probability) to backend/scorecard_log.jsonl.

This is the dataset for the live **model-vs-market tournament-forecast scorecard**:
the model's edge thesis is forecasting tournament *outcomes* (advancement, group
winner, reach-stage-X, title) — not single games — so as each stage resolves we
score these stored probabilities (Brier / log-loss) against reality, and against
the bookmaker where we have their odds for the same market.

We log every team's stage probabilities each day:
  r32 (= advance from group), r16, quarter, semi, final, champion,
plus current group points/played and the de-vigged bookmaker *title* probability
(the only futures market we currently capture — see fetch_odds.py).

NOTE: bookmaker *advancement / group-winner* odds are NOT in the the-odds-api
free tier we use, so the book column here is title-only. To make the
"book hasn't eliminated them yet" comparison punchy, capture per-market
advancement odds separately and join on (date, team).

Run:  python3 -m log_scorecard [API_BASE]
      python3 log_scorecard.py https://...run.app
Idempotent: one row per canonical date (re-running a logged date is a no-op).
"""
import json, os, sys, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "scorecard_log.jsonl")
ODDS = os.path.join(HERE, "odds_snapshot.json")
API_DEFAULT = "https://vm2026-api-704772753584.europe-west1.run.app"


def fetch_canonical(api_base):
    url = api_base.rstrip("/") + "/api/canonical"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def book_title_probs(teams):
    """De-vig the committed odds snapshot into a per-team (sv key) title prob."""
    if not os.path.exists(ODDS):
        return {}
    odds = json.load(open(ODDS, encoding="utf-8"))
    en2sv = {t["name_en"]: t["team"] for t in teams}
    en2sv["Bosnia and Herzegovina"] = en2sv.get("Bosnia")
    acc = defaultdict(list)
    for book, od in odds.items():
        inv = {t: 1.0 / v for t, v in od.items() if v and v > 1}
        s = sum(inv.values())
        if s <= 0:
            continue
        for t, p in inv.items():
            acc[t].append(p / s)
    return {en2sv[t]: sum(v) / len(v) for t, v in acc.items() if t in en2sv}


def standings(d):
    pts = defaultdict(int); played = defaultdict(int)
    for g, ms in d.get("group_matches", {}).items():
        for m in ms:
            if m.get("result"):
                h, a = m["home"], m["away"]; hg, ag = m["result"]["home"], m["result"]["away"]
                played[h] += 1; played[a] += 1
                if hg > ag: pts[h] += 3
                elif ag > hg: pts[a] += 3
                else: pts[h] += 1; pts[a] += 1
    return pts, played


def main():
    api = sys.argv[1] if len(sys.argv) > 1 else API_DEFAULT
    d = fetch_canonical(api)
    date = d.get("date")
    if not date:
        sys.exit("canonical has no date; aborting")

    # idempotent: skip if this date is already logged
    if os.path.exists(LOG):
        for line in open(LOG, encoding="utf-8"):
            if line.strip() and json.loads(line).get("date") == date:
                print(f"scorecard: {date} already logged — no-op")
                return

    teams = d.get("teams", [])
    book = book_title_probs(teams)
    pts, played = standings(d)
    rec = {"date": date, "n": d.get("n"), "teams": []}
    for t in teams:
        sv = t["team"]
        rec["teams"].append({
            "team": t["name_en"], "group": t["group"],
            "pts": pts[sv], "played": played[sv],
            # model stage probabilities (r32 = advance from group)
            "m_r32": round(t.get("r32", 0), 5), "m_r16": round(t.get("r16", 0), 5),
            "m_quarter": round(t.get("quarter", 0), 5), "m_semi": round(t.get("semi", 0), 5),
            "m_final": round(t.get("final", 0), 5), "m_champion": round(t.get("champion", 0), 5),
            # bookmaker (title market only, for now)
            "b_champion": round(book.get(sv, 0.0), 5),
        })
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"scorecard: logged {date} ({len(rec['teams'])} teams) -> {LOG}")


if __name__ == "__main__":
    main()
