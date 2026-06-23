#!/usr/bin/env python3
"""
Fetch live 2026 World Cup results and write them into backend/fixtures.json.

Primary source: football-data.org v4 (free tier covers competition WC). It is
reliable for the schedule/status/teams (matched by stable TLA codes) but its
free tier can LAG on scores (a match shows FINISHED with score null for a
while) — so we only write a result when the score is actually present, and the
martj42 / scrape fallbacks fill anything still missing.

fixtures.json is the single source of truth for tournament results:
  * group_stage[i]["result"] = {"home": hs, "away": as} (oriented to the fixture)
  * ko_results = [{round, home_team, away_team, home, away, winner, date}]
build_elo reads these for the Elo walk-forward (ignoring martj42's own WC rows
in-window, so a UTC date offset can't double-count), and the forecast builds its
conditioning `cond` from them.

Run:  python3 -m fitting.fetch_results        (needs FOOTBALL_DATA_KEY in the
                                               environment — get a free key at
                                               https://www.football-data.org/)
"""

import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(os.path.dirname(HERE), "fixtures.json")
API = "https://api.football-data.org/v4/competitions/WC/matches"
KEY = os.environ.get("FOOTBALL_DATA_KEY")  # free key: https://www.football-data.org/

# football-data TLA -> engine Swedish key. TLAs are stable FIFA codes, so this
# is robust to name-spelling drift ("Congo DR", "Czechia", "Türkiye", ...).
TLA_SV = {
    "ALG": "Algeriet", "ARG": "Argentina", "AUS": "Australien", "AUT": "Österrike",
    "BEL": "Belgien", "BIH": "Bosnien", "BRA": "Brasilien", "CAN": "Kanada",
    "CIV": "Elfenbenskusten", "COD": "DR Kongo", "COL": "Colombia",
    "CPV": "Kap Verde", "CRO": "Kroatien", "CUW": "Curacao", "CZE": "Tjeckien",
    "ECU": "Ecuador", "EGY": "Egypten", "ENG": "England", "ESP": "Spanien",
    "FRA": "Frankrike", "GER": "Tyskland", "GHA": "Ghana", "HAI": "Haiti",
    "IRN": "Iran", "IRQ": "Irak", "JOR": "Jordanien", "JPN": "Japan",
    "KOR": "Sydkorea", "KSA": "Saudiarabien", "MAR": "Marocko", "MEX": "Mexiko",
    "NED": "Nederländerna", "NOR": "Norge", "NZL": "Nya Zeeland", "PAN": "Panama",
    "PAR": "Paraguay", "POR": "Portugal", "QAT": "Qatar", "RSA": "Sydafrika",
    "SCO": "Skottland", "SEN": "Senegal", "SUI": "Schweiz", "SWE": "Sverige",
    "TUN": "Tunisien", "TUR": "Turkiet", "URY": "Uruguay", "URU": "Uruguay",
    "USA": "USA",
    "UZB": "Uzbekistan",
}
_STAGE_ROUND = {
    "LAST_32": "R32", "LAST_16": "R16", "QUARTER_FINALS": "QF",
    "SEMI_FINALS": "SF", "THIRD_PLACE": "3rd", "FINAL": "Final",
}


def _fetch():
    if not KEY:
        sys.exit("Set FOOTBALL_DATA_KEY in the environment "
                 "(free key at https://www.football-data.org/).")
    req = urllib.request.Request(API, headers={"X-Auth-Token": KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    fx = json.load(open(FIXTURES, encoding="utf-8"))
    data = _fetch()
    matches = data.get("matches", [])

    # Index group fixtures by the (frozenset of teams) for orientation-free match.
    group_by_pair = {frozenset((m["home"], m["away"])): m for m in fx["group_stage"]}
    ko_results = {}  # frozenset(teams) -> record (dedup by pair)

    finished = written_group = written_ko = no_score = unmatched = 0
    for m in matches:
        if m.get("status") != "FINISHED":
            continue
        finished += 1
        ft = (m.get("score") or {}).get("fullTime") or {}
        hs, as_ = ft.get("home"), ft.get("away")
        if hs is None or as_ is None:
            no_score += 1
            continue
        ht, at = m["homeTeam"].get("tla"), m["awayTeam"].get("tla")
        h, a = TLA_SV.get(ht), TLA_SV.get(at)
        if not h or not a:
            unmatched += 1
            print(f"  ? unmapped TLA: {ht} / {at}", file=sys.stderr)
            continue
        date = m["utcDate"][:10]
        stage = m.get("stage")
        if stage == "GROUP_STAGE":
            fxm = group_by_pair.get(frozenset((h, a)))
            if not fxm:
                unmatched += 1
                continue
            # Orient to the fixture's home/away.
            fxm["result"] = ({"home": hs, "away": as_} if fxm["home"] == h
                             else {"home": as_, "away": hs})
            written_group += 1
        else:
            rnd = _STAGE_ROUND.get(stage, stage)
            winner = h if hs > as_ else (a if as_ > hs else None)
            # football-data exposes penalties for KO draws; use them for winner.
            if winner is None:
                pens = (m.get("score") or {}).get("penalties") or {}
                ph, pa = pens.get("home"), pens.get("away")
                if ph is not None and pa is not None:
                    winner = h if ph > pa else a
            ko_results[frozenset((h, a))] = {
                "round": rnd, "date": date, "home_team": h, "away_team": a,
                "home": hs, "away": as_, "winner": winner}
            written_ko += 1

    fx["ko_results"] = list(ko_results.values())
    with open(FIXTURES, "w", encoding="utf-8") as f:
        json.dump(fx, f, ensure_ascii=False, indent=2)

    played_group = sum(1 for m in fx["group_stage"] if m["result"])
    print(f"football-data: {finished} finished; wrote {written_group} group + "
          f"{written_ko} ko results; {no_score} finished-but-no-score (fallback "
          f"needed); {unmatched} unmatched.")
    print(f"fixtures.json now has {played_group}/72 group results recorded.")


if __name__ == "__main__":
    main()
