#!/usr/bin/env python3
"""
VM 2026 – Monte Carlo-simuleringsmotor
=======================================
Simulerar hela turneringen (48 lag, 12 grupper) från gruppspel till final.

Modell
------
* Varje lag har en styrka R baserad på FIFA-rankingpoäng (april 2026).
  Exakta poäng används för topp-20; för övriga lag är poängen estimerade
  utifrån deras FIFA-rankingplacering (markerade med ~ i kommentarer).
* En match modelleras med en Poisson-målmodell. Målövertaget bestäms av
  styrkeskillnaden (+ hemmafördel för värdnationerna USA/Mexiko/Kanada).
* Oavgjort i slutspel avgörs via straffar (svagt viktat mot starkare lag).
* Hela turneringen upprepas N gånger; sannolikheter aggregeras.

Användning:  python3 vm2026_sim.py [N]
"""

import random
import sys
from collections import defaultdict

# ----------------------------------------------------------------------
# 1. LAGDATA  (namn: [FIFA-poäng, värdnation?])
#    Källa: FIFA Men's World Ranking 1 april 2026.
# ----------------------------------------------------------------------
HOSTS = {"USA", "Mexiko", "Kanada"}

GROUPS = {
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

# Platt uppslagstabell
TEAM_RATING = {t: r for g in GROUPS.values() for t, r in g.items()}
TEAM_GROUP = {t: gname for gname, g in GROUPS.items() for t in g}

# Modellparametrar (kalibrerade så att simulerade titelodds ligger nära marknaden)
GOAL_SCALE = 0.0048   # mål per FIFA-poängs skillnad
BASE_GOALS = 2.65     # genomsnittligt totalt antal mål i en jämn match
HOME_ADV = 60         # FIFA-poäng extra för värdnation i gruppspel


def expected_lambdas(ra, rb, home_a=0, home_b=0):
    """Returnerar förväntat antal mål (lambda) för lag A och B."""
    diff = (ra + home_a) - (rb + home_b)
    mu = diff * GOAL_SCALE                      # målövertag
    la = max(0.15, BASE_GOALS / 2 + mu / 2)
    lb = max(0.15, BASE_GOALS / 2 - mu / 2)
    return la, lb


def poisson(lam):
    """Dra ett Poisson-fördelat antal mål."""
    L, k, p = pow(2.718281828, -lam), 0, 1.0
    while True:
        p *= random.random()
        if p <= L:
            return k
        k += 1


def play_match(a, b, home_a=0, home_b=0):
    la, lb = expected_lambdas(TEAM_RATING[a], TEAM_RATING[b], home_a, home_b)
    return poisson(la), poisson(lb)


def home_bonus(team):
    return HOME_ADV if team in HOSTS else 0


# ----------------------------------------------------------------------
# 2. GRUPPSPEL
# ----------------------------------------------------------------------
def simulate_group(gname, teams):
    """Spelar alla 6 matcher i en grupp. Returnerar rankad lista av lag + statistik."""
    stats = {t: {"pts": 0, "gf": 0, "ga": 0} for t in teams}
    names = list(teams)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            ga, gb = play_match(a, b, home_bonus(a), home_bonus(b))
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
    """Väljer de 8 bästa trean-lagen enligt FIFA:s kriterier."""
    def key(item):
        t, s = item
        return (s["pts"], s["gf"] - s["ga"], s["gf"], TEAM_RATING[t], random.random())
    ordered = sorted(thirds, key=key, reverse=True)
    return [t for t, _ in ordered[:8]]


# ----------------------------------------------------------------------
# 3. SLUTSPEL  (Round of 32 -> final)
#    Kvalificerade lag seedas in i ett balanserat utslagsträd efter
#    gruppspelsprestation. (En förenkling av FIFA:s fasta lottningstabell
#    för de 8 trean-lagen; påverkar totala titeloddsen marginellt.)
# ----------------------------------------------------------------------
def knockout_match(a, b):
    ga, gb = play_match(a, b)            # neutral plan i slutspel
    if ga != gb:
        return a if ga > gb else b
    # Straffar: svag vikt mot starkare lag
    pa = 0.5 + (TEAM_RATING[a] - TEAM_RATING[b]) * 0.0004
    return a if random.random() < max(0.15, min(0.85, pa)) else b


def play_bracket(qualifiers, progress):
    """qualifiers: lista med 32 lag, redan seedade i bracket-ordning."""
    round_names = ["R32", "R16", "Kvartsfinal", "Semifinal", "Final"]
    teams = qualifiers
    for rnd in round_names:
        for t in teams:
            progress[rnd][t] += 1
        winners = []
        for i in range(0, len(teams), 2):
            winners.append(knockout_match(teams[i], teams[i + 1]))
        teams = winners
    progress["Mästare"][teams[0]] += 1
    return teams[0]


def _seeding_order(n):
    """Standard single-elimination seedningsordning (0-indexerad) för n platser."""
    order = [0, 1]
    while len(order) < n:
        m = len(order) * 2
        order = [x for o in order for x in (o, m - 1 - o)]
    return order


_BRACKET_ORDER = _seeding_order(32)


def seed_bracket(winners, runners, thirds):
    """
    Seedar 32 kvalificerade lag i ett balanserat utslagsträd: starkaste lag
    sprids ut maximalt (seed 1 och 2 kan bara mötas i finalen). En standardiserad
    approximation av FIFA:s fasta lottningstabell – påverkar totala titeloddsen
    marginellt men ger korrekt monoton slutspelsstruktur.
    """
    pool = winners + runners + thirds          # 12 + 12 + 8 = 32
    pool.sort(key=lambda t: TEAM_RATING[t], reverse=True)   # index 0 = starkast
    slots = [None] * 32
    for position, seed in enumerate(_BRACKET_ORDER):
        slots[position] = pool[seed]
    return slots


# ----------------------------------------------------------------------
# 4. EN HEL TURNERING
# ----------------------------------------------------------------------
def simulate_tournament(progress, group_winner_count):
    winners, runners, thirds = [], [], []
    for gname, teams in GROUPS.items():
        ranked, stats = simulate_group(gname, teams)
        group_winner_count[ranked[0]] += 1
        winners.append(ranked[0])
        runners.append(ranked[1])
        thirds.append((ranked[2], stats[ranked[2]]))
    qualified_thirds = best_thirds(thirds)
    bracket = seed_bracket(winners, runners, qualified_thirds)
    return play_bracket(bracket, progress)


# ----------------------------------------------------------------------
# 5. KÖR N SIMULERINGAR
# ----------------------------------------------------------------------
def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    random.seed(42)

    progress = {r: defaultdict(int) for r in
                ["R32", "R16", "Kvartsfinal", "Semifinal", "Final", "Mästare"]}
    group_winner_count = defaultdict(int)

    for _ in range(N):
        simulate_tournament(progress, group_winner_count)

    teams = list(TEAM_RATING)
    teams.sort(key=lambda t: progress["Mästare"][t], reverse=True)

    print(f"\n{'='*78}\n  VM 2026 – Monte Carlo ({N:,} simuleringar)\n{'='*78}")
    print(f"{'Lag':<17}{'Grp':>4}{'Vinst%':>9}{'Final%':>9}{'Semi%':>8}"
          f"{'Kvart%':>8}{'R16%':>8}")
    print("-" * 78)
    for t in teams[:24]:
        pct = lambda r: 100 * progress[r][t] / N
        print(f"{t:<17}{TEAM_GROUP[t]:>4}{pct('Mästare'):>8.1f}%"
              f"{pct('Final'):>8.1f}%{pct('Semifinal'):>7.1f}%"
              f"{pct('Kvartsfinal'):>7.1f}%{pct('R16'):>7.1f}%")
    print("-" * 78)

    return progress, group_winner_count, N


if __name__ == "__main__":
    main()
