"""
Historical FIFA ranking as-of-date lookup (Dato-Futbol archive, 1992-2024).
Points are z-scored within each ranking date, which makes the signal robust to
the Aug-2018 points-formula regime change (each snapshot is standardised on its
own distribution). Team names are mapped from FIFA-official style to the
results-dataset style. Used by M6 to tune the Elo/FIFA rankings weight.
"""
import bisect
import csv
import math
import os

DATA = os.path.join(os.path.dirname(__file__), "data", "fifa_ranking.csv")

# FIFA-official -> results-dataset team name (lowercased). Only real mismatches.
_ALIAS = {
    "korea republic": "south korea", "korea dpr": "north korea", "ir iran": "iran",
    "usa": "united states", "côte d'ivoire": "ivory coast", "cabo verde": "cape verde",
    "china pr": "china", "congo dr": "dr congo", "czechia": "czech republic",
    "türkiye": "turkey", "kyrgyz republic": "kyrgyzstan", "the gambia": "gambia",
    "st. kitts and nevis": "saint kitts and nevis", "st. lucia": "saint lucia",
    "st. vincent / grenadines": "saint vincent and the grenadines",
    "brunei darussalam": "brunei", "são tomé e príncipe": "são tomé and príncipe",
}


def canon(name):
    k = name.strip().lower()
    return _ALIAS.get(k, k)


_DATES = []     # sorted ranking-date strings
_SNAP = []      # parallel: {canon_team: zscore} per date


def _load():
    if _DATES:
        return
    by_date = {}
    with open(DATA, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pts = r["total_points"]
            if pts in ("", "NA"):
                continue
            by_date.setdefault(r["date"], []).append((canon(r["team"]), float(pts)))
    for d in sorted(by_date):
        rows = by_date[d]
        xs = [p for _, p in rows]
        mean = sum(xs) / len(xs)
        std = math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs)) or 1.0
        _DATES.append(d)
        _SNAP.append({t: (p - mean) / std for t, p in rows})


def zscore(team_canon, date_str):
    """FIFA points z-score for a team as of the latest ranking date <= date_str,
    or None if unavailable."""
    _load()
    i = bisect.bisect_right(_DATES, date_str) - 1
    if i < 0:
        return None
    return _SNAP[i].get(team_canon)
