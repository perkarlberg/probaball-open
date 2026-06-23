#!/usr/bin/env python3
"""
Build backend/fixtures.json — the official 2026 FIFA World Cup schedule + bracket.

Source: Wikipedia "2026 FIFA World Cup" (group stage + knockout stage) and the
ESPN official fixture list (group match numbers/dates/cities), captured 2026-06.

The output is the backbone for tournament mode:
  * group_stage  — 72 matches, concrete teams (engine Swedish keys), dated, with
                   a `result` field filled in as games are played.
  * knockout     — 32 matches (R32 73-88, R16 89-96, QF 97-100, SF 101-102,
                   3rd 103, Final 104). Teams are POSITIONAL specs until known:
                     {"type":"W","group":"E"}      winner of group E
                     {"type":"R","group":"A"}      runner-up of group A
                     {"type":"3","eligible":[...]} a best-third from these groups
                     {"type":"WM","match":74}      winner of match 74
                     {"type":"LM","match":101}      loser of match 101 (3rd place)
  * third_place_slots — the 8 R32 slots that receive a best-third, each with its
                   FIFA eligible-group set (drives the third-place assignment).
  * round_dates  — per-round date ranges.

Team names are stored as the engine's Swedish keys so the engine/store consume
them directly; the frontend localizes from those keys.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # backend/ on path
from model_data import NAME_EN_SV  # noqa: E402

# Schedule uses "United States"; the engine key is "USA".
_ALIAS = {"United States": "USA"}


def sv(name_en: str) -> str:
    key = _ALIAS.get(name_en, name_en)
    s = NAME_EN_SV.get(key)
    if s is None:
        raise SystemExit(f"Unmapped team name: {name_en!r}")
    return s


# (match_no, date, group, team1_en, team2_en, city)
GROUP_FIXTURES = [
    (1, "2026-06-11", "A", "Mexico", "South Africa", "Mexico City"),
    (2, "2026-06-11", "A", "South Korea", "Czechia", "Zapopan"),
    (3, "2026-06-12", "B", "Canada", "Bosnia and Herzegovina", "Toronto"),
    (4, "2026-06-12", "D", "United States", "Paraguay", "Inglewood"),
    (5, "2026-06-13", "B", "Qatar", "Switzerland", "Santa Clara"),
    (6, "2026-06-13", "C", "Brazil", "Morocco", "East Rutherford"),
    (7, "2026-06-13", "C", "Haiti", "Scotland", "Foxborough"),
    (8, "2026-06-13", "D", "Australia", "Turkey", "Vancouver"),
    (9, "2026-06-14", "E", "Germany", "Curacao", "Houston"),
    (10, "2026-06-14", "F", "Netherlands", "Japan", "Arlington"),
    (11, "2026-06-14", "E", "Ivory Coast", "Ecuador", "Philadelphia"),
    (12, "2026-06-14", "F", "Sweden", "Tunisia", "Guadalupe"),
    (13, "2026-06-15", "H", "Spain", "Cape Verde", "Atlanta"),
    (14, "2026-06-15", "G", "Belgium", "Egypt", "Seattle"),
    (15, "2026-06-15", "H", "Saudi Arabia", "Uruguay", "Miami Gardens"),
    (16, "2026-06-15", "G", "Iran", "New Zealand", "Inglewood"),
    (17, "2026-06-16", "I", "France", "Senegal", "East Rutherford"),
    (18, "2026-06-16", "I", "Iraq", "Norway", "Foxborough"),
    (19, "2026-06-16", "J", "Argentina", "Algeria", "Kansas City"),
    (20, "2026-06-16", "J", "Austria", "Jordan", "Santa Clara"),
    (21, "2026-06-17", "K", "Portugal", "DR Congo", "Houston"),
    (22, "2026-06-17", "L", "England", "Croatia", "Arlington"),
    (23, "2026-06-17", "L", "Ghana", "Panama", "Toronto"),
    (24, "2026-06-17", "K", "Uzbekistan", "Colombia", "Mexico City"),
    (25, "2026-06-18", "A", "Czechia", "South Africa", "Atlanta"),
    (26, "2026-06-18", "B", "Switzerland", "Bosnia and Herzegovina", "Inglewood"),
    (27, "2026-06-18", "B", "Canada", "Qatar", "Vancouver"),
    (28, "2026-06-18", "A", "Mexico", "South Korea", "Zapopan"),
    (29, "2026-06-19", "D", "United States", "Australia", "Seattle"),
    (30, "2026-06-19", "C", "Scotland", "Morocco", "Foxborough"),
    (31, "2026-06-19", "C", "Brazil", "Haiti", "Philadelphia"),
    (32, "2026-06-19", "D", "Turkey", "Paraguay", "Santa Clara"),
    (33, "2026-06-20", "F", "Netherlands", "Sweden", "Houston"),
    (34, "2026-06-20", "E", "Germany", "Ivory Coast", "Toronto"),
    (35, "2026-06-20", "E", "Ecuador", "Curacao", "Kansas City"),
    (36, "2026-06-20", "F", "Tunisia", "Japan", "Guadalupe"),
    (37, "2026-06-21", "H", "Spain", "Saudi Arabia", "Atlanta"),
    (38, "2026-06-21", "G", "Belgium", "Iran", "Inglewood"),
    (39, "2026-06-21", "H", "Uruguay", "Cape Verde", "Miami Gardens"),
    (40, "2026-06-21", "G", "New Zealand", "Egypt", "Vancouver"),
    (41, "2026-06-22", "J", "Argentina", "Austria", "Arlington"),
    (42, "2026-06-22", "I", "France", "Iraq", "Philadelphia"),
    (43, "2026-06-22", "I", "Norway", "Senegal", "East Rutherford"),
    (44, "2026-06-22", "J", "Jordan", "Algeria", "Santa Clara"),
    (45, "2026-06-23", "K", "Portugal", "Uzbekistan", "Houston"),
    (46, "2026-06-23", "L", "England", "Ghana", "Foxborough"),
    (47, "2026-06-23", "L", "Panama", "Croatia", "Toronto"),
    (48, "2026-06-23", "K", "Colombia", "DR Congo", "Zapopan"),
    (49, "2026-06-24", "B", "Switzerland", "Canada", "Vancouver"),
    (50, "2026-06-24", "B", "Bosnia and Herzegovina", "Qatar", "Seattle"),
    (51, "2026-06-24", "C", "Scotland", "Brazil", "Miami Gardens"),
    (52, "2026-06-24", "C", "Morocco", "Haiti", "Atlanta"),
    (53, "2026-06-24", "A", "Czechia", "Mexico", "Mexico City"),
    (54, "2026-06-24", "A", "South Africa", "South Korea", "Guadalupe"),
    (55, "2026-06-25", "E", "Ecuador", "Germany", "East Rutherford"),
    (56, "2026-06-25", "E", "Curacao", "Ivory Coast", "Philadelphia"),
    (57, "2026-06-25", "F", "Japan", "Sweden", "Arlington"),
    (58, "2026-06-25", "F", "Tunisia", "Netherlands", "Kansas City"),
    (59, "2026-06-25", "D", "Turkey", "United States", "Inglewood"),
    (60, "2026-06-25", "D", "Paraguay", "Australia", "Santa Clara"),
    (61, "2026-06-26", "I", "Norway", "France", "Foxborough"),
    (62, "2026-06-26", "I", "Senegal", "Iraq", "Toronto"),
    (63, "2026-06-26", "H", "Cape Verde", "Saudi Arabia", "Houston"),
    (64, "2026-06-26", "H", "Uruguay", "Spain", "Zapopan"),
    (65, "2026-06-26", "G", "Egypt", "Iran", "Seattle"),
    (66, "2026-06-26", "G", "New Zealand", "Belgium", "Vancouver"),
    (67, "2026-06-27", "L", "Panama", "England", "East Rutherford"),
    (68, "2026-06-27", "L", "Croatia", "Ghana", "Philadelphia"),
    (69, "2026-06-27", "K", "Colombia", "Portugal", "Miami Gardens"),
    (70, "2026-06-27", "K", "DR Congo", "Uzbekistan", "Atlanta"),
    (71, "2026-06-27", "J", "Algeria", "Austria", "Kansas City"),
    (72, "2026-06-27", "J", "Jordan", "Argentina", "Arlington"),
]

# R32 slots that receive a best-third, with their FIFA eligible-group sets.
THIRD_SLOTS = {
    74: ["A", "B", "C", "D", "F"],
    77: ["C", "D", "F", "G", "H"],
    79: ["C", "E", "F", "H", "I"],
    80: ["E", "H", "I", "J", "K"],
    81: ["B", "E", "F", "I", "J"],
    82: ["A", "E", "H", "I", "J"],
    85: ["E", "F", "G", "I", "J"],
    87: ["D", "E", "I", "J", "L"],
}


def W(g):
    return {"type": "W", "group": g}


def R(g):
    return {"type": "R", "group": g}


def T(mno):
    return {"type": "3", "eligible": THIRD_SLOTS[mno]}


def WM(m):
    return {"type": "WM", "match": m}


def LM(m):
    return {"type": "LM", "match": m}


# (match_no, round, date, home_spec, away_spec, city)
KNOCKOUT = [
    (73, "R32", "2026-06-28", R("A"), R("B"), "Inglewood"),
    (74, "R32", "2026-06-29", W("E"), T(74), "Foxborough"),
    (75, "R32", "2026-06-29", W("F"), R("C"), "Guadalupe"),
    (76, "R32", "2026-06-29", W("C"), R("F"), "Houston"),
    (77, "R32", "2026-06-30", W("I"), T(77), "East Rutherford"),
    (78, "R32", "2026-06-30", R("E"), R("I"), "Arlington"),
    (79, "R32", "2026-06-30", W("A"), T(79), "Mexico City"),
    (80, "R32", "2026-07-01", W("L"), T(80), "Atlanta"),
    (81, "R32", "2026-07-01", W("D"), T(81), "Santa Clara"),
    (82, "R32", "2026-07-01", W("G"), T(82), "Seattle"),
    (83, "R32", "2026-07-02", R("K"), R("L"), "Toronto"),
    (84, "R32", "2026-07-02", W("H"), R("J"), "Inglewood"),
    (85, "R32", "2026-07-02", W("B"), T(85), "Vancouver"),
    (86, "R32", "2026-07-03", W("J"), R("H"), "Miami Gardens"),
    (87, "R32", "2026-07-03", W("K"), T(87), "Kansas City"),
    (88, "R32", "2026-07-03", R("D"), R("G"), "Arlington"),
    (89, "R16", "2026-07-04", WM(74), WM(77), "Philadelphia"),
    (90, "R16", "2026-07-04", WM(73), WM(75), "Houston"),
    (91, "R16", "2026-07-05", WM(76), WM(78), "East Rutherford"),
    (92, "R16", "2026-07-05", WM(79), WM(80), "Mexico City"),
    (93, "R16", "2026-07-06", WM(83), WM(84), "Arlington"),
    (94, "R16", "2026-07-06", WM(81), WM(82), "Seattle"),
    (95, "R16", "2026-07-07", WM(86), WM(88), "Atlanta"),
    (96, "R16", "2026-07-07", WM(85), WM(87), "Vancouver"),
    (97, "QF", "2026-07-09", WM(89), WM(90), "Foxborough"),
    (98, "QF", "2026-07-10", WM(93), WM(94), "Inglewood"),
    (99, "QF", "2026-07-11", WM(91), WM(92), "Miami Gardens"),
    (100, "QF", "2026-07-11", WM(95), WM(96), "Kansas City"),
    (101, "SF", "2026-07-14", WM(97), WM(98), "Arlington"),
    (102, "SF", "2026-07-15", WM(99), WM(100), "Atlanta"),
    (103, "3rd", "2026-07-18", LM(101), LM(102), "Miami Gardens"),
    (104, "Final", "2026-07-19", WM(101), WM(102), "East Rutherford"),
]

ROUND_DATES = {
    "group_stage": {"start": "2026-06-11", "end": "2026-06-27"},
    "round_of_32": {"start": "2026-06-28", "end": "2026-07-03"},
    "round_of_16": {"start": "2026-07-04", "end": "2026-07-07"},
    "quarter_finals": {"start": "2026-07-09", "end": "2026-07-11"},
    "semi_finals": {"start": "2026-07-14", "end": "2026-07-15"},
    "third_place": {"date": "2026-07-18"},
    "final": {"date": "2026-07-19"},
}


def main():
    group_stage = [
        {"match_no": mno, "date": d, "group": g,
         "home": sv(t1), "away": sv(t2), "city": city, "result": None}
        for (mno, d, g, t1, t2, city) in GROUP_FIXTURES
    ]
    knockout = [
        {"match_no": mno, "round": rnd, "date": d,
         "home": h, "away": a, "city": city, "result": None}
        for (mno, rnd, d, h, a, city) in KNOCKOUT
    ]
    out = {
        "_source": "Wikipedia 2026 FIFA World Cup (group + knockout) + ESPN fixtures, captured 2026-06",
        "round_dates": ROUND_DATES,
        "third_place_slots": {str(k): v for k, v in THIRD_SLOTS.items()},
        "group_stage": group_stage,
        "knockout": knockout,
    }
    path = os.path.join(os.path.dirname(HERE), "fixtures.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {path}: {len(group_stage)} group matches + {len(knockout)} knockout matches")


if __name__ == "__main__":
    main()
