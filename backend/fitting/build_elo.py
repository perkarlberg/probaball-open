"""
Offline step (M2): compute current World-Football Elo for the 48 tournament
teams from the historical results dataset, and write backend/elo_ratings.json
for the runtime model to load. Re-run when results.csv is refreshed:

  cd backend && python3 -m fitting.build_elo
"""
import csv
import datetime
import json
import os

from backtest.elo import Elo

DATA = os.path.join(os.path.dirname(__file__), "..", "backtest", "data", "results.csv")
# Committed gap-fill for matches martj42 hasn't ingested yet (e.g. the pre-WC
# warm-up friendlies). Merged + deduped with results.csv; a no-op once martj42
# catches up. Add rows here for live results the upstream dataset still lacks.
EXTRA = os.path.join(os.path.dirname(__file__), "warmup_results.csv")
OUT = os.path.join(os.path.dirname(__file__), "..", "elo_ratings.json")
# Live World Cup results are authoritative in fixtures.json (written by
# fetch_results). build_elo feeds them into the Elo walk-forward and drops any
# WC rows martj42/warmup carry in the tournament window, so a UTC date offset
# between sources can't double-count a tournament match.
FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures.json")
WC_START = "2026-06-11"
# Include every completed match up to and including today (UTC). martj42 lags,
# so this rarely excludes anything — but a hardcoded date silently drops fresh
# results (e.g. pre-WC warm-ups) on every refresh until bumped.
TODAY = datetime.date.today().isoformat()

# Engine team key (Swedish) -> name as it appears in results.csv.
TEAM_DATASET = {
    "Mexiko": "Mexico", "Sydafrika": "South Africa", "Sydkorea": "South Korea",
    "Tjeckien": "Czech Republic", "Kanada": "Canada", "Schweiz": "Switzerland",
    "Qatar": "Qatar", "Bosnien": "Bosnia and Herzegovina", "Brasilien": "Brazil",
    "Marocko": "Morocco", "Skottland": "Scotland", "Haiti": "Haiti",
    "USA": "United States", "Paraguay": "Paraguay", "Australien": "Australia",
    "Turkiet": "Turkey", "Tyskland": "Germany", "Curacao": "Curaçao",
    "Elfenbenskusten": "Ivory Coast", "Ecuador": "Ecuador",
    "Nederländerna": "Netherlands", "Japan": "Japan", "Tunisien": "Tunisia",
    "Sverige": "Sweden", "Belgien": "Belgium", "Egypten": "Egypt", "Iran": "Iran",
    "Nya Zeeland": "New Zealand", "Spanien": "Spain", "Kap Verde": "Cape Verde",
    "Saudiarabien": "Saudi Arabia", "Uruguay": "Uruguay", "Frankrike": "France",
    "Senegal": "Senegal", "Norge": "Norway", "Irak": "Iraq",
    "Argentina": "Argentina", "Algeriet": "Algeria", "Österrike": "Austria",
    "Jordanien": "Jordan", "Portugal": "Portugal", "Colombia": "Colombia",
    "Uzbekistan": "Uzbekistan", "DR Kongo": "DR Congo", "England": "England",
    "Kroatien": "Croatia", "Ghana": "Ghana", "Panama": "Panama",
}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _wc_rows_from_fixtures():
    """World Cup results recorded in fixtures.json, as Elo rows (dataset names).
    All marked neutral=TRUE — the tournament is on neutral ground for almost
    everyone; the sim applies the host edge separately."""
    if not os.path.exists(FIXTURES):
        return []
    fx = json.load(open(FIXTURES, encoding="utf-8"))

    def row(date, home_sv, away_sv, hs, as_):
        return {"date": date, "home_team": TEAM_DATASET[home_sv],
                "away_team": TEAM_DATASET[away_sv], "home_score": str(hs),
                "away_score": str(as_), "tournament": "FIFA World Cup",
                "neutral": "TRUE"}

    out = []
    for m in fx.get("group_stage", []):
        res = m.get("result")
        if res:
            out.append(row(m["date"], m["home"], m["away"], res["home"], res["away"]))
    for r in fx.get("ko_results", []):
        out.append(row(r["date"], r["home_team"], r["away_team"], r["home"], r["away"]))
    return out


def main():
    elo = Elo()  # home_adv=85
    rows = _load(DATA)
    # Merge committed gap-fill rows that martj42 doesn't have yet (deduped).
    seen = {(r["date"], r["home_team"], r["away_team"]) for r in rows}
    n_extra = 0
    if os.path.exists(EXTRA):
        for r in _load(EXTRA):
            key = (r["date"], r["home_team"], r["away_team"])
            if key not in seen:
                rows.append(r)
                seen.add(key)
                n_extra += 1
    # Tournament results from fixtures.json (authoritative). Drop any WC rows the
    # other sources carry in-window first, then append, to avoid double-counting.
    wc_rows = _wc_rows_from_fixtures()
    n_wc = len(wc_rows)
    if wc_rows:
        rows = [r for r in rows
                if not (r.get("tournament") == "FIFA World Cup" and r["date"] >= WC_START)]
        rows.extend(wc_rows)
    rows = [r for r in rows
            if r["home_score"] not in ("", "NA") and r["away_score"] not in ("", "NA")
            and r["date"] <= TODAY]
    rows.sort(key=lambda r: r["date"])
    for r in rows:
        elo.update(r["home_team"], r["away_team"], int(r["home_score"]),
                   int(r["away_score"]), r["tournament"],
                   r["neutral"].strip().lower() == "true")

    out = {}
    for sv, ds in TEAM_DATASET.items():
        if ds not in elo.r:
            raise SystemExit(f"no Elo for {sv} ({ds!r})")
        out[sv] = round(elo.r[ds], 1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)

    last = max(r["date"] for r in rows)
    print(f"wrote {OUT} (Elo as of {last}; +{n_extra} gap-fill rows)")
    for sv, e in sorted(out.items(), key=lambda x: -x[1])[:10]:
        print(f"  {sv:16} {e}")


if __name__ == "__main__":
    main()
