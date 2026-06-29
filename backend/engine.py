#!/usr/bin/env python3
"""
VM 2026 - Monte Carlo simulation engine (library form)
======================================================
Refactored from the original ``vm2026_sim.py`` CLI script into an importable
module that takes parameters and returns structured data, instead of printing
to stdout with a hard-coded RNG seed.

The match model is byte-for-byte identical to the validated original:
  * bivariate-Poisson goals driven by the FIFA-rating gap,
  * host bonus in the group stage only,
  * shootouts mildly biased toward the stronger side.

See ``METHODOLOGY.md`` for data sources and modelling assumptions.

Public API:
  * ``DEFAULT_PARAMS`` / ``Params``  - model constants (overridable per call)
  * ``run_simulation(n, params)``    - aggregate N tournaments -> dict
  * ``sample_bracket(params)``       - one representative bracket tree -> dict

A thin ``__main__`` keeps the old CLI behaviour (``python3 engine.py [N]``).
"""

from __future__ import annotations

import math
import random
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass

# ----------------------------------------------------------------------
# 1. TEAM DATA  (name: FIFA points)
#    Source: FIFA Men's World Ranking, 1 April 2026 release.
#    Top-20 points are exact; lower-ranked points are interpolated estimates
#    (see METHODOLOGY.md section 6). Groups are authoritative (Final Draw
#    5 Dec 2025 + playoffs 26/31 Mar 2026) and must not change before kickoff.
# ----------------------------------------------------------------------
HOSTS = {"USA", "Mexiko", "Kanada"}

GROUPS: dict[str, dict[str, int]] = {
    "A": {"Mexiko": 1681, "Sydafrika": 1400, "Sydkorea": 1585, "Tjeckien": 1490},
    "B": {"Kanada": 1560, "Schweiz": 1649, "Qatar": 1420, "Bosnien": 1375},
    "C": {"Brasilien": 1761, "Marocko": 1756, "Skottland": 1480, "Haiti": 1300},
    "D": {"USA": 1673, "Paraguay": 1495, "Australien": 1575, "Turkiet": 1575},
    "E": {"Tyskland": 1730, "Curacao": 1305, "Elfenbenskusten": 1530, "Ecuador": 1600},
    "F": {"Nederländerna": 1758, "Japan": 1660, "Tunisien": 1470, "Sverige": 1505},
    "G": {"Belgien": 1735, "Egypten": 1565, "Iran": 1615, "Nya Zeeland": 1295},
    "H": {"Spanien": 1876, "Kap Verde": 1360, "Saudiarabien": 1395, "Uruguay": 1673},
    "I": {"Frankrike": 1877, "Senegal": 1689, "Norge": 1555, "Irak": 1410},
    "J": {"Argentina": 1875, "Algeriet": 1570, "Österrike": 1595, "Jordanien": 1385},
    "K": {"Portugal": 1764, "Colombia": 1693, "Uzbekistan": 1440, "DR Kongo": 1460},
    "L": {"England": 1826, "Kroatien": 1717, "Ghana": 1340, "Panama": 1535},
}

# Flat lookups, derived from GROUPS (the single source of truth).
FIFA_RATING: dict[str, int] = {t: r for g in GROUPS.values() for t, r in g.items()}
TEAM_GROUP: dict[str, str] = {t: gname for gname, g in GROUPS.items() for t in g}

# Effective rating drives the match model. It blends FIFA points with bookmaker
# odds and expert predictions (1/3 each); see model_data.py. If model_data is
# unavailable or has no external data, it degrades to pure FIFA ratings.
try:
    import model_data
    TEAM_RATING: dict[str, float] = model_data.blended_ratings(FIFA_RATING)
    TEAM_SIGNALS: dict[str, dict] = model_data.team_signals(FIFA_RATING)
except Exception:  # pragma: no cover
    TEAM_RATING = dict(FIFA_RATING)
    TEAM_SIGNALS = {t: {"fifa_rating": r, "fifa_field_rank": None,
                        "fifa_world_rank": None, "book_prob": None,
                        "expert_prob": None, "effective_rating": float(r)}
                    for t, r in FIFA_RATING.items()}

ROUND_NAMES = ["R32", "R16", "Kvartsfinal", "Semifinal", "Final"]


@dataclass(frozen=True)
class Params:
    """Tunable model constants. goal_scale/base_goals/home_adv are calibrated so
    title odds track the market (the blend includes it); the backtest goal-model
    fit (0.0052/2.72) confirmed these are close. rho is the Dixon-Coles low-score
    correction fit on historical results."""

    goal_scale: float = 0.0048   # goals per rating-point gap
    base_goals: float = 2.65     # avg total goals in an even match
    # Host edge. Home advantage in football is well established (Pollard, 1986);
    # we calibrate the magnitude on our model's performance across previous World
    # Cups, so it's as well-supported as the data we have. Group-stage value here;
    # reduced in the knockouts (ko_host_adv).
    home_adv: float = 60.0       # rating bonus for hosts (group stage)
    rho: float = -0.06           # Dixon-Coles low-score correction (data-fit)
    ko_host_adv: float = 30.0    # reduced host edge in knockouts (M8; on home soil)


DEFAULT_PARAMS = Params()

# Sensible UI guardrails so a tweaked rerun stays in a meaningful regime.
PARAM_BOUNDS = {
    "goal_scale": (0.0, 0.02),
    "base_goals": (0.5, 6.0),
    "home_adv": (0.0, 300.0),
    "rho": (-0.18, 0.05),  # Dixon-Coles draw correction; UI exposes -rho as "draw tendency"
}


def coerce_params(raw: dict | None) -> Params:
    """Build a Params from untrusted input, clamping to PARAM_BOUNDS."""
    if not raw:
        return DEFAULT_PARAMS
    vals = {}
    for field, (lo, hi) in PARAM_BOUNDS.items():
        v = raw.get(field, getattr(DEFAULT_PARAMS, field))
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = getattr(DEFAULT_PARAMS, field)
        vals[field] = max(lo, min(hi, v))
    return Params(**vals)


MAX_FORCED = 20


def coerce_forced(raw) -> dict:
    """
    Build a forced-outcome lookup from untrusted input. Input is a list of
    {a, b, winner}; output maps a sorted (a, b) tuple -> winner. Entries with
    unknown teams, a winner not in the pair, or self-matches are dropped.
    """
    out: dict[tuple, str] = {}
    if not raw:
        return out
    for item in list(raw)[:MAX_FORCED]:
        try:
            a, b, w = item["a"], item["b"], item["winner"]
        except (TypeError, KeyError):
            continue
        if a == b or a not in TEAM_RATING or b not in TEAM_RATING:
            continue
        if w not in (a, b):
            continue
        out[tuple(sorted((a, b)))] = w
    return out


def _forced_winner(forced, a, b):
    return forced.get(tuple(sorted((a, b)))) if forced else None


# ----------------------------------------------------------------------
# 2. MATCH MODEL  (identical to the validated original)
# ----------------------------------------------------------------------
def expected_lambdas(ra, rb, p: Params, home_a=0, home_b=0):
    """Expected goals (lambda) for teams A and B."""
    diff = (ra + home_a) - (rb + home_b)
    mu = diff * p.goal_scale
    la = max(0.15, p.base_goals / 2 + mu / 2)
    lb = max(0.15, p.base_goals / 2 - mu / 2)
    return la, lb


def poisson(lam):
    """Draw a Poisson-distributed goal count (Knuth's algorithm)."""
    L, k, prod = pow(2.718281828, -lam), 0, 1.0
    while True:
        prod *= random.random()
        if prod <= L:
            return k
        k += 1


def _tau(i, j, la, lb, rho):
    """Dixon-Coles low-score dependence factor (1.0 outside the 2x2 corner)."""
    if i == 0 and j == 0:
        return 1.0 - la * lb * rho
    if i == 0 and j == 1:
        return 1.0 + la * rho
    if i == 1 and j == 0:
        return 1.0 + lb * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def dc_sample(la, lb, rho):
    """Sample (goals_a, goals_b) from the Dixon-Coles-adjusted joint Poisson
    via accept-reject (~1.1 proposals/match; corrects the low-score draw bias)."""
    if not rho:
        return poisson(la), poisson(lb)
    M = max(1.0, _tau(0, 0, la, lb, rho), _tau(0, 1, la, lb, rho),
            _tau(1, 0, la, lb, rho), _tau(1, 1, la, lb, rho))
    for _ in range(16):
        i, j = poisson(la), poisson(lb)
        tau = _tau(i, j, la, lb, rho) if (i < 2 and j < 2) else 1.0
        if random.random() * M <= tau:
            return i, j
    return i, j


def _sample_outcome(a, b, p, home_a, home_b, oc, tries=40):
    """Sample a Dixon-Coles scoreline consistent with a forced W/D/L outcome
    (``oc`` is "draw" or the winning team) — for scenario fan-out, where we fix a
    match's result but not its exact score. Rejection sampling from the model's
    own goal distribution; falls back to a minimal consistent scoreline."""
    la, lb = expected_lambdas(TEAM_RATING[a], TEAM_RATING[b], p, home_a, home_b)
    for _ in range(tries):
        ga, gb = dc_sample(la, lb, p.rho)
        if oc == "draw":
            if ga == gb:
                return ga, gb
        elif oc == a:
            if ga > gb:
                return ga, gb
        else:  # oc == b
            if gb > ga:
                return ga, gb
    return (1, 1) if oc == "draw" else ((1, 0) if oc == a else (0, 1))


def play_match(a, b, p: Params, home_a=0, home_b=0, forced=None, cond=None):
    # Tournament conditioning takes precedence over everything: a played match
    # contributes its actual scoreline; a scenario forces a W/D/L outcome.
    if cond is not None:
        key = frozenset((a, b))
        res = cond.get("results", {}).get(key)
        if res is not None:
            return res[a], res[b]
        oc = cond.get("outcomes", {}).get(key)
        if oc is not None:
            return _sample_outcome(a, b, p, home_a, home_b, oc)
    w = _forced_winner(forced, a, b)
    if w is not None:
        # User-set "conviction" result: the chosen side wins 1-0.
        return (1, 0) if w == a else (0, 1)
    la, lb = expected_lambdas(TEAM_RATING[a], TEAM_RATING[b], p, home_a, home_b)
    return dc_sample(la, lb, p.rho)


def home_bonus(team, p: Params):
    return p.home_adv if team in HOSTS else 0


# ----------------------------------------------------------------------
# 3. GROUP STAGE
# ----------------------------------------------------------------------
def simulate_group(teams, p: Params, forced=None, cond=None):
    """Play all 6 matches in a group. Returns (ranked teams, stats)."""
    stats = {t: {"pts": 0, "gf": 0, "ga": 0} for t in teams}
    names = list(teams)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            ga, gb = play_match(a, b, p, home_bonus(a, p), home_bonus(b, p), forced, cond)
            stats[a]["gf"] += ga; stats[a]["ga"] += gb
            stats[b]["gf"] += gb; stats[b]["ga"] += ga
            if ga > gb:
                stats[a]["pts"] += 3
            elif gb > ga:
                stats[b]["pts"] += 3
            else:
                stats[a]["pts"] += 1; stats[b]["pts"] += 1

    def key(t):
        s = stats[t]
        return (s["pts"], s["gf"] - s["ga"], s["gf"], TEAM_RATING[t], random.random())

    ranked = sorted(names, key=key, reverse=True)
    return ranked, stats


def best_thirds(thirds):
    """Pick the 8 best third-placed teams. thirds: [(group, team, stats)] ->
    [(group, team)] for the eight qualifiers, by the FIFA-style ranking key."""
    def key(item):
        g, t, s = item
        return (s["pts"], s["gf"] - s["ga"], s["gf"], TEAM_RATING[t], random.random())
    ordered = sorted(thirds, key=key, reverse=True)
    return [(g, t) for g, t, _ in ordered[:8]]


# Standard FIFA 4-team group fixture order by draw position (0-3), three
# matchdays of two games each.
GROUP_SCHEDULE = [(0, 1), (2, 3), (0, 2), (3, 1), (0, 3), (1, 2)]


def _match_outcome(la, lb, rho, maxg=8):
    """From the Dixon-Coles goal distribution, return the win/draw/loss
    probabilities and the modal scoreline. W/D/L is the meaningful summary; the
    single most-likely exact score is almost always low (1-1/1-0) and is kept
    only as a footnote."""
    pa = [math.exp(-la)]
    pb = [math.exp(-lb)]
    for k in range(1, maxg + 1):
        pa.append(pa[-1] * la / k)
        pb.append(pb[-1] * lb / k)
    home = draw = away = 0.0
    best, best_p = (0, 0), -1.0
    for i in range(maxg + 1):
        for j in range(maxg + 1):
            tau = _tau(i, j, la, lb, rho) if (i < 2 and j < 2) else 1.0
            p = pa[i] * pb[j] * tau
            if i > j:
                home += p
            elif i == j:
                draw += p
            else:
                away += p
            if p > best_p:
                best_p, best = p, (i, j)
    s = home + draw + away
    return best, home / s, draw / s, away / s


def group_fixtures(p: Params):
    """Win/draw/loss probabilities of every group match, in tournament schedule
    order (3 matchdays x 2 games). Deterministic from the model (no simulation).
    The modal scoreline is included as a footnote only -- the W/D/L split is the
    meaningful summary (the single most-likely exact score clusters at 1-1/1-0)."""
    out = {}
    for g, teams in GROUPS.items():
        names = list(teams)
        ms = []
        for k, (i, j) in enumerate(GROUP_SCHEDULE):
            a, b = names[i], names[j]
            la, lb = expected_lambdas(TEAM_RATING[a], TEAM_RATING[b], p,
                                      home_bonus(a, p), home_bonus(b, p))
            (hg, ag), ph, pd, pa = _match_outcome(la, lb, p.rho)
            ms.append({"home": a, "away": b, "hg": hg, "ag": ag,
                       "p_home": round(ph, 4), "p_draw": round(pd, 4),
                       "p_away": round(pa, 4), "matchday": k // 2 + 1})
        out[g] = ms
    return out


# ----------------------------------------------------------------------
# 4. KNOCKOUT BRACKET  (R32 -> final)
# ----------------------------------------------------------------------
def knockout_match(a, b, p: Params, record: list | None = None, forced=None, cond=None):
    forced_w = _forced_winner(forced, a, b)
    # Host nations keep a reduced home edge in the knockouts (matches in NA, on
    # or near home soil); cancels if both teams are hosts.
    ha = p.ko_host_adv if a in HOSTS else 0
    hb = p.ko_host_adv if b in HOSTS else 0
    ga, gb = play_match(a, b, p, ha, hb, forced, cond)
    shootout = False
    if ga != gb:
        winner = a if ga > gb else b
    else:
        pa = 0.5 + (TEAM_RATING[a] - TEAM_RATING[b]) * 0.0004
        winner = a if random.random() < max(0.15, min(0.85, pa)) else b
        shootout = True
    # A played knockout decided on penalties: fix the team that actually advanced
    # (the scoreline alone can't tell us the shootout result).
    if cond is not None:
        adv = cond.get("advanced", {}).get(frozenset((a, b)))
        if adv is not None:
            winner = adv
    if record is not None:
        record.append({"a": a, "b": b, "ga": ga, "gb": gb, "winner": winner,
                       "shootout": shootout, "forced": forced_w is not None})
    return winner


# Official 2026 Round-of-32 layout. Each R32 match is a pair of slots; a slot is
# ("W", g)=group winner, ("R", g)=runner-up, ("3", g)=the third-placed team that
# faces group g's winner. The match order is arranged so the sequential-pairs
# play_bracket folds into FIFA's exact R16->QF->SF->final tree (matches 73-104,
# Wikipedia "2026 FIFA World Cup knockout stage"). The eight third slots are tied
# to the winners of groups A,B,D,E,G,I,K,L (confirmed from FIFA's Annex C table).
_R32_LAYOUT = [
    (("W", "E"), ("3", "E")),  (("W", "I"), ("3", "I")),   # M74, M77
    (("R", "A"), ("R", "B")),  (("W", "F"), ("R", "C")),   # M73, M75
    (("R", "K"), ("R", "L")),  (("W", "H"), ("R", "J")),   # M83, M84
    (("W", "D"), ("3", "D")),  (("W", "G"), ("3", "G")),   # M81, M82
    (("W", "C"), ("R", "F")),  (("R", "E"), ("R", "I")),   # M76, M78
    (("W", "A"), ("3", "A")),  (("W", "L"), ("3", "L")),   # M79, M80
    (("W", "J"), ("R", "H")),  (("R", "D"), ("R", "G")),   # M86, M88
    (("W", "B"), ("3", "B")),  (("W", "K"), ("3", "K")),   # M85, M87
]
_THIRD_SLOTS = [g for pair in _R32_LAYOUT for kind, g in pair if kind == "3"]


# FIFA's official R32 third-place combination eligibility. Each third-place slot
# sits opposite a group winner (the slot is labelled by that winner's group) and
# may ONLY be filled by a best-third from one of these groups. (2026 knockout
# bracket, Wikipedia "Combinations of matches in the round of 32".) The winner
# pairings in _R32_LAYOUT are already correct; this is what the old heuristic
# (just "avoid your own group's winner") got wrong.
_THIRD_ELIGIBLE = {
    "E": {"A", "B", "C", "D", "F"},  # M74
    "I": {"C", "D", "F", "G", "H"},  # M77
    "A": {"C", "E", "F", "H", "I"},  # M79
    "L": {"E", "H", "I", "J", "K"},  # M80
    "D": {"B", "E", "F", "I", "J"},  # M81
    "G": {"A", "E", "H", "I", "J"},  # M82
    "B": {"E", "F", "G", "I", "J"},  # M85
    "K": {"D", "E", "I", "J", "L"},  # M87
}


# FIFA's official third-place allocation is a fixed lookup keyed by WHICH eight
# groups' thirds qualify — per-slot eligibility (_THIRD_ELIGIBLE) alone does NOT
# determine it, because several valid matchings can satisfy the constraints while
# FIFA's table picks one specific assignment. Pinned for the sets we actually
# need (verified against the published bracket); falls back to eligibility
# backtracking for any other set (e.g. pre-tournament sims over many combos).
# Key = frozenset of qualifying groups; value = {slot-winner-group: third-group}.
_THIRD_ALLOCATION = {
    # 2026 actual R32 (thirds from B,D,E,F,I,J,K,L). Verified vs Wikipedia/CBS/Yahoo:
    # France(WI)-Sweden(3F), Germany(WE)-Paraguay(3D), Mexico(WA)-Ecuador(3E),
    # Belgium(WG)-Senegal(3I), USA(WD)-Bosnia(3B), England(WL)-DRCongo(3K),
    # Switzerland(WB)-Algeria(3J), Colombia(WK)-Ghana(3L).
    frozenset("BDEFIJKL"): {"E": "D", "I": "F", "A": "E", "L": "K",
                            "D": "B", "G": "I", "B": "J", "K": "L"},
}


def _assign_thirds(slot_groups, qualified):
    """Match the 8 qualifying thirds to the third-place slots. Uses FIFA's pinned
    official allocation when the qualifying set is known; otherwise backtracks
    over _THIRD_ELIGIBLE (a slot labelled by the group winner it sits opposite may
    only take a third from _THIRD_ELIGIBLE[label]). qualified: [(group, team)] ->
    {slot_label: team}."""
    g2t = {g: team for g, team in qualified}
    alloc = _THIRD_ALLOCATION.get(frozenset(g2t))
    if alloc and all(tg in g2t for tg in alloc.values()):
        return {slot: g2t[tg] for slot, tg in alloc.items()}

    def match(eligible_fn):
        used = [False] * len(qualified)
        res = {}

        def bt(i):
            if i == len(slot_groups):
                return True
            for k, (g, team) in enumerate(qualified):
                if not used[k] and eligible_fn(slot_groups[i], g):
                    used[k] = True
                    res[slot_groups[i]] = team
                    if bt(i + 1):
                        return True
                    used[k] = False
            return False

        return res if bt(0) else None

    return (match(lambda slot, g: g in _THIRD_ELIGIBLE[slot])
            or match(lambda slot, g: g != slot)
            or {})


def seed_bracket(winners, runners, qualified_thirds):
    """Place qualifiers into FIFA's fixed R32 slots. winners/runners: {group:
    team}; qualified_thirds: [(group, team)] (the 8 best). Returns the 32-slot
    bracket array in play_bracket order."""
    third_of = _assign_thirds(_THIRD_SLOTS, qualified_thirds)

    def resolve(spec):
        kind, g = spec
        if kind == "W":
            return winners[g]
        if kind == "R":
            return runners[g]
        return third_of[g]

    slots = []
    for s1, s2 in _R32_LAYOUT:
        slots.append(resolve(s1))
        slots.append(resolve(s2))
    return slots


def _qualify(p: Params, forced=None, cond=None):
    """Run the group stage once and return the seeded 32-team bracket."""
    winners, runners, thirds = {}, {}, []
    group_positions = {}
    for gname, teams in GROUPS.items():
        ranked, stats = simulate_group(teams, p, forced, cond)
        group_positions[gname] = ranked
        winners[gname] = ranked[0]
        runners[gname] = ranked[1]
        thirds.append((gname, ranked[2], stats[ranked[2]]))
    qualified_thirds = best_thirds(thirds)
    bracket = seed_bracket(winners, runners, qualified_thirds)
    return bracket, group_positions


# ----------------------------------------------------------------------
# 5. AGGREGATION OVER N TOURNAMENTS
# ----------------------------------------------------------------------
def run_simulation(n: int = 1000, params: Params | None = None,
                   podium_tries: int = 40000, forced=None, cond=None) -> dict:
    """
    Simulate ``n`` full tournaments and aggregate per-team stage probabilities
    and per-group finishing-position distributions. ``forced`` is a coerced
    forced-outcome lookup ((a,b)->winner). ``cond`` is tournament conditioning
    (played results + scenario-forced outcomes), keyed by frozenset({a,b}) — see
    play_match. Also returns a sample bracket whose podium (gold/silver/bronze)
    matches the three most probable teams. Returns a JSON-serialisable dict.
    """
    p = params or DEFAULT_PARAMS
    progress = {r: defaultdict(int) for r in ROUND_NAMES + ["Mästare"]}
    # group -> team -> [P(1st), P(2nd), P(3rd), P(4th)] counts
    group_pos = {g: {t: [0, 0, 0, 0] for t in GROUPS[g]} for g in GROUPS}

    # Per-team opponent tally for every knockout round, so we can project each
    # team's path. Conditioned on the team reaching that round.
    opp = {r: {} for r in ROUND_NAMES}

    for _ in range(n):
        bracket, positions = _qualify(p, forced, cond)
        for gname, ranked in positions.items():
            for pos, team in enumerate(ranked):
                group_pos[gname][team][pos] += 1
        teams = bracket
        for rnd in ROUND_NAMES:
            for t in teams:
                progress[rnd][t] += 1
            oc = opp.get(rnd)
            if oc is not None:
                for i in range(0, len(teams), 2):
                    a, b = teams[i], teams[i + 1]
                    oc.setdefault(a, {})[b] = oc.setdefault(a, {}).get(b, 0) + 1
                    oc.setdefault(b, {})[a] = oc.setdefault(b, {}).get(a, 0) + 1
            teams = [knockout_match(teams[i], teams[i + 1], p, None, forced, cond)
                     for i in range(0, len(teams), 2)]
        progress["Mästare"][teams[0]] += 1

    # Matchups already played (group + recorded KO), as frozensets, so a team's
    # already-contested round isn't re-shown as an upcoming game.
    played = ((set(cond.get("results", {})) | set(cond.get("advanced", {})))
              if cond else set())

    def ko_path(team):
        """The team's path from its next game to the final: each round it is >50%
        to REACH. A round whose opponent is already determined (share==1, e.g. the
        R32 once groups are done) carries a W/D/L prediction; later rounds stay
        projected (most-likely opponent + the odds of facing them)."""
        out = []
        for rnd in ROUND_NAMES:
            reach = progress[rnd][team] / n
            c = opp[rnd].get(team)
            if reach <= 0.5 or not c:
                continue
            name = max(c, key=c.get)
            if frozenset((team, name)) in played:
                continue  # they have already played this round
            entry = {"round": rnd, "opp": name,
                     "opp_name_en": TEAM_SIGNALS.get(name, {}).get("name_en"),
                     "reach": round(reach, 3),
                     "opp_share": round(c[name] / sum(c.values()), 3),
                     "known": c[name] == sum(c.values())}
            if entry["known"]:
                # Opponent fixed -> betting breakdown for BOTH teams. A KO tie has
                # no draw: advance = regulation win + (90' draw won in ET/pens).
                # Mirrors knockout_match exactly (same goal model + shootout edge).
                ha = p.ko_host_adv if team in HOSTS else 0
                hb = p.ko_host_adv if name in HOSTS else 0
                la, lb = expected_lambdas(TEAM_RATING[team], TEAM_RATING[name], p, ha, hb)
                _, reg, draw, opp_reg = _match_outcome(la, lb, p.rho)
                ps = min(0.85, max(0.15, 0.5 + (TEAM_RATING[team] - TEAM_RATING[name]) * 0.0004))
                entry.update({"reg": round(reg, 3), "et": round(draw * ps, 3),
                              "opp_reg": round(opp_reg, 3), "opp_et": round(draw * (1 - ps), 3),
                              "advance": round(reg + draw * ps, 3),
                              "opp_advance": round(opp_reg + draw * (1 - ps), 3)})
            out.append(entry)
        return out

    # Per-team stage probabilities + external signals, sorted by title prob.
    team_rows = []
    for t in TEAM_RATING:
        sig = TEAM_SIGNALS.get(t, {})
        team_rows.append({
            "team": t,
            "name_en": sig.get("name_en"),
            "group": TEAM_GROUP[t],
            "rating": round(TEAM_RATING[t], 1),
            "fifa_rating": sig.get("fifa_rating"),
            "fifa_world_rank": sig.get("fifa_world_rank"),
            "fifa_field_rank": sig.get("fifa_field_rank"),
            "elo": sig.get("elo"),
            "book_prob": sig.get("book_prob"),
            "book_odds_avg": sig.get("book_odds_avg"),
            "book_count": sig.get("book_count"),
            "expert_prob": sig.get("expert_prob"),
            "expert_mentions": sig.get("expert_mentions"),
            "book_odds": sig.get("book_odds"),
            "experts": sig.get("experts"),
            "r32": progress["R32"][t] / n,
            "champion": progress["Mästare"][t] / n,
            "final": progress["Final"][t] / n,
            "semi": progress["Semifinal"][t] / n,
            "quarter": progress["Kvartsfinal"][t] / n,
            "r16": progress["R16"][t] / n,
            "next_ko": ko_path(t),
        })
    team_rows.sort(key=lambda r: (r["champion"], r["final"], r["rating"]), reverse=True)

    groups_out = {}
    for gname in GROUPS:
        rows = []
        for t in GROUPS[gname]:
            counts = group_pos[gname][t]
            rows.append({
                "team": t,
                "rating": TEAM_RATING[t],
                "p_first": counts[0] / n,
                "p_second": counts[1] / n,
                "p_third": counts[2] / n,
                "p_fourth": counts[3] / n,
                # expected finishing position (lower = better)
                "expected_pos": sum((i + 1) * c for i, c in enumerate(counts)) / n,
            })
        rows.sort(key=lambda r: r["expected_pos"])
        groups_out[gname] = rows

    ranked_names = [r["team"] for r in team_rows]
    bracket, search = find_representative_bracket(p, ranked_names,
                                                  max_tries=podium_tries,
                                                  forced=forced, cond=cond)

    try:
        model = model_data.model_meta()
    except Exception:  # pragma: no cover
        model = None

    return {
        "n": n,
        "params": asdict(p),
        "teams": team_rows,
        "groups": groups_out,
        "group_matches": group_fixtures(p),
        "top": ranked_names[:8],
        "top3": ranked_names[:3],
        "sample_bracket": bracket,
        "bracket_search": search,
        "model": model,
    }


def sample_bracket(params: Params | None = None, forced=None, cond=None) -> dict:
    """
    Run a single tournament and return its full bracket tree - one realisation.
    Each round is a list of match records {a, b, ga, gb, winner, shootout}.
    """
    p = params or DEFAULT_PARAMS
    bracket, group_positions = _qualify(p, forced, cond)
    rounds = []
    teams = bracket
    for rnd in ROUND_NAMES:
        record: list = []
        teams = [knockout_match(teams[i], teams[i + 1], p, record, forced, cond)
                 for i in range(0, len(teams), 2)]
        rounds.append({"round": rnd, "matches": record})
    return {
        "champion": teams[0],
        "rounds": rounds,
        "groups": group_positions,
    }


def _losers(matches):
    return [m["a"] if m["winner"] == m["b"] else m["b"] for m in matches]


def _bracket_finish(b: dict):
    """(champion, runner_up, set(SF losers), set(QF losers)) from a bracket."""
    champion = b["champion"]
    fm = b["rounds"][-1]["matches"][0]
    runner_up = fm["a"] if fm["winner"] == fm["b"] else fm["b"]
    sf_losers = set(_losers(b["rounds"][-2]["matches"]))   # 2 teams
    qf_losers = set(_losers(b["rounds"][-3]["matches"]))   # 4 teams
    return champion, runner_up, sf_losers, qf_losers


def find_representative_bracket(params: Params | None, ranked: list,
                                max_tries: int = 40000, forced=None, cond=None):
    """
    Find the single sampled tournament that best illustrates the *expected*
    outcome, by lexicographic (nested) scoring against the ranking ``ranked``
    (teams ordered by title probability). In priority order, prefer a run where:
      1. the champion is the most probable winner (ranked[0]),
      2. the beaten finalist is the most probable 2nd (ranked[1]),
      3. as many of the most probable 3rd & 4th are the losing semifinalists,
      4. as many of the most probable 5th-8th are the losing quarter-finalists.
    Criteria 3 and 4 are graded (overlap counts, not all-or-nothing) so the
    chosen run is always a coherent chalk bracket even when a perfectly seeded
    run never occurs in the sample. Keeps the best score tuple; stops early on a
    perfect (1, 1, 2, 4). Returns (bracket_with_podium, search_info).
    """
    p = params or DEFAULT_PARAMS
    top = ranked[:8]
    want_champ, want_ru = top[0], top[1]
    want_sf = set(top[2:4])
    want_qf = set(top[4:8])
    best, best_score, best_k = None, (-1,), max_tries
    for k in range(1, max_tries + 1):
        b = sample_bracket(p, forced, cond)
        champ, ru, sf, qf = _bracket_finish(b)
        score = (int(champ == want_champ), int(ru == want_ru),
                 len(sf & want_sf), len(qf & want_qf))
        if score > best_score:
            best, best_score, best_k = b, score, k
            if score == (1, 1, 2, 4):
                break

    champ, ru, sf, qf = _bracket_finish(best)
    bronze = top[2] if top[2] in sf else (next(iter(sf)) if sf else None)
    best["podium"] = {"gold": champ, "silver": ru, "bronze": bronze}
    return best, {
        "tries": best_k,
        "exact": best_score == (1, 1, 2, 4),
        "match": {
            "champion": bool(best_score[0]),
            "runner_up": bool(best_score[1]),
            "semifinalists": best_score[2],   # 0..2 of {3rd,4th}
            "quarterfinalists": best_score[3],  # 0..4 of {5th..8th}
        },
    }


# ----------------------------------------------------------------------
# 6. CLI (preserves the original behaviour for quick local checks)
# ----------------------------------------------------------------------
def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    random.seed(42)
    result = run_simulation(n)
    print(f"\n{'='*78}\n  VM 2026 - Monte Carlo ({n:,} simulations)\n{'='*78}")
    print(f"{'Lag':<17}{'Grp':>4}{'Vinst%':>9}{'Final%':>9}{'Semi%':>8}"
          f"{'Kvart%':>8}{'R16%':>8}")
    print("-" * 78)
    for row in result["teams"][:24]:
        print(f"{row['team']:<17}{row['group']:>4}{row['champion']*100:>8.1f}%"
              f"{row['final']*100:>8.1f}%{row['semi']*100:>7.1f}%"
              f"{row['quarter']*100:>7.1f}%{row['r16']*100:>7.1f}%")
    print("-" * 78)


if __name__ == "__main__":
    main()
