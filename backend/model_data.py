"""
External model inputs and blending: FIFA rating + bookmaker odds + expert picks.

The simulator's match model is driven by a single per-team "effective rating".
We build that rating by blending three independent signals with equal weight
(1/3 each):

  1. FIFA World Ranking points (from engine.GROUPS).
  2. Bookmaker implied title probability (de-vigged average across books).
  3. Expert prediction weight (aggregated notable-expert picks).

Blending is done in z-score space and rescaled to the FIFA rating mean/std, so
the resulting effective ratings stay on the same scale the Poisson model was
calibrated for. Teams missing bookmaker/expert data fall back to their FIFA
z-score for the missing component(s), so they are neither rewarded nor punished
for absent data.

BOOKMAKER_ODDS / EXPERT_PICKS / FIFA_RANK are populated from web research (late
May 2026). If they are empty, blending degenerates to pure FIFA ratings.
"""

from __future__ import annotations

import json
import math
import os

# Walk-forward World-Football Elo for the 48 teams (built offline by
# fitting/build_elo.py from historical results). Empty if the file is absent,
# in which case the rankings bucket falls back to FIFA only.
try:
    with open(os.path.join(os.path.dirname(__file__), "elo_ratings.json"),
              encoding="utf-8") as _f:
        ELO_RATING: dict[str, float] = json.load(_f)
except Exception:  # pragma: no cover
    ELO_RATING = {}

# Sub-weights within the rankings bucket. The M6 backtest (backtest/compare_fifa.py)
# found FIFA adds no predictive value beyond Elo (its marginal coefficient is
# negative and it raises out-of-sample RPS), so FIFA is kept only as a light
# robustness anchor.
RANK_W = (0.85, 0.15)  # (Elo, FIFA)

# Overall blend weights (rankings=Elo, bookmaker, expert). Elo and the market
# carry the forecast (equal); experts get a light 5% — enough to nudge the order
# (a human-judgment voice) without overriding the two harder, sharper signals.
# At 20% the sparse pre-tournament expert picks overrode Elo+market and flipped
# the favourite; 5% lets them count without dictating. Not match-RPS-tunable
# (no historical odds/picks) — set by intent + the live in-tournament grading.
BLEND_W = (0.475, 0.475, 0.05)

# Engine uses Swedish team names; research returns English. Map EN -> SV.
NAME_EN_SV = {
    "Mexico": "Mexiko", "South Africa": "Sydafrika", "South Korea": "Sydkorea",
    "Czechia": "Tjeckien", "Canada": "Kanada", "Switzerland": "Schweiz",
    "Qatar": "Qatar", "Bosnia and Herzegovina": "Bosnien", "Bosnia": "Bosnien",
    "Brazil": "Brasilien", "Morocco": "Marocko", "Scotland": "Skottland",
    "Haiti": "Haiti", "USA": "USA", "Paraguay": "Paraguay",
    "Australia": "Australien", "Turkey": "Turkiet", "Germany": "Tyskland",
    "Curacao": "Curacao", "Ivory Coast": "Elfenbenskusten", "Ecuador": "Ecuador",
    "Netherlands": "Nederländerna", "Japan": "Japan", "Tunisia": "Tunisien",
    "Sweden": "Sverige", "Belgium": "Belgien", "Egypt": "Egypten", "Iran": "Iran",
    "New Zealand": "Nya Zeeland", "Spain": "Spanien", "Cape Verde": "Kap Verde",
    "Saudi Arabia": "Saudiarabien", "Uruguay": "Uruguay", "France": "Frankrike",
    "Senegal": "Senegal", "Norway": "Norge", "Iraq": "Irak",
    "Argentina": "Argentina", "Algeria": "Algeriet", "Austria": "Österrike",
    "Jordan": "Jordanien", "Portugal": "Portugal", "Colombia": "Colombia",
    "Uzbekistan": "Uzbekistan", "DR Congo": "DR Kongo", "England": "England",
    "Croatia": "Kroatien", "Ghana": "Ghana", "Panama": "Panama",
}


def to_sv(name: str) -> str | None:
    return NAME_EN_SV.get(name, name if name in NAME_EN_SV.values() else None)


# ---------------------------------------------------------------------------
# Source data (English keys as collected; converted to SV at load). POPULATED
# FROM RESEARCH. Empty => pure-FIFA fallback.
# ---------------------------------------------------------------------------

# team(EN) -> {book_name: american_odds_int}. Source: ESPN/DraftKings full
# 48-team table + FanDuel/BetMGM/Kalshi for the top favorites, dated 26-29 May
# 2026 (see sources in research notes). DraftKings covers all 48; other books
# cover ~top 10-13.
BOOKMAKER_ODDS: dict[str, dict[str, int]] = {
    "Spain": {"DraftKings": 475, "FanDuel": 450, "BetMGM": 500, "Kalshi": 488},
    "France": {"DraftKings": 500, "FanDuel": 490, "BetMGM": 450, "Kalshi": 499},
    "England": {"DraftKings": 650, "FanDuel": 650, "BetMGM": 650, "Kalshi": 801},
    "Brazil": {"DraftKings": 850, "FanDuel": 800, "BetMGM": 800, "Kalshi": 987},
    "Argentina": {"DraftKings": 900, "FanDuel": 900, "BetMGM": 800, "Kalshi": 975},
    "Portugal": {"DraftKings": 1000, "FanDuel": 1000, "BetMGM": 1000, "Kalshi": 953},
    "Germany": {"DraftKings": 1400, "FanDuel": 1300, "BetMGM": 1400, "Kalshi": 1686},
    "Netherlands": {"DraftKings": 2200, "FanDuel": 1800, "BetMGM": 2000, "Kalshi": 2400},
    "Belgium": {"DraftKings": 3500, "FanDuel": 2200, "Kalshi": 4067},
    "Norway": {"DraftKings": 3500, "FanDuel": 3300, "BetMGM": 2500, "Kalshi": 4067},
    "Colombia": {"DraftKings": 4000, "FanDuel": 4500},
    "Uruguay": {"DraftKings": 5000, "FanDuel": 6000},
    "Morocco": {"DraftKings": 5000},
    "USA": {"DraftKings": 6000, "FanDuel": 6000},
    "Switzerland": {"DraftKings": 6500},
    "Japan": {"DraftKings": 6500},
    "Mexico": {"DraftKings": 8000},
    "Croatia": {"DraftKings": 8000},
    "Ecuador": {"DraftKings": 8000},
    "Senegal": {"DraftKings": 9000},
    "Turkey": {"DraftKings": 10000},
    "Sweden": {"DraftKings": 10000},
    "Austria": {"DraftKings": 15000},
    "Canada": {"DraftKings": 20000},
    "Scotland": {"DraftKings": 20000},
    "Ivory Coast": {"DraftKings": 25000},
    "Czechia": {"DraftKings": 25000},
    "Paraguay": {"DraftKings": 30000},
    "Egypt": {"DraftKings": 30000},
    "Ghana": {"DraftKings": 30000},
    "Algeria": {"DraftKings": 35000},
    "South Korea": {"DraftKings": 40000},
    "Bosnia and Herzegovina": {"DraftKings": 50000},
    "Tunisia": {"DraftKings": 50000},
    "Australia": {"DraftKings": 60000},
    "Iran": {"DraftKings": 70000},
    "DR Congo": {"DraftKings": 100000},
    "Saudi Arabia": {"DraftKings": 100000},
    "South Africa": {"DraftKings": 100000},
    "Panama": {"DraftKings": 100000},
    "Cape Verde": {"DraftKings": 100000},
    "Qatar": {"DraftKings": 150000},
    "Uzbekistan": {"DraftKings": 150000},
    "New Zealand": {"DraftKings": 150000},
    "Iraq": {"DraftKings": 150000},
    "Jordan": {"DraftKings": 250000},
    "Curacao": {"DraftKings": 250000},
    "Haiti": {"DraftKings": 250000},
}

# FanDuel/BetMGM/Kalshi above were frozen pre-tournament (26-29 May) snapshots.
# Once the tournament started those go stale; the live odds snapshot now carries
# the bookmaker leg. FanDuel (via FOX Sports) and Kalshi (its own API) re-enter
# LIVE through fetch_odds, so their frozen columns are dropped here and the live
# values take over. BetMGM has no cleanly-attributable feed, so it stays gone
# rather than diluting the leg with 3-week-old priors. DraftKings stays as the
# all-48 long-tail fallback — the live snapshot's DraftKings overrides it
# per-team wherever the-odds-api prices a team.
for _row in BOOKMAKER_ODDS.values():
    for _stale in ("FanDuel", "BetMGM", "Kalshi"):
        _row.pop(_stale, None)

# DECIMAL-odds books, merged into BOOKMAKER_ODDS via the de-vig pipeline
# (american_to_prob) after conversion. Populated entirely from the live odds
# snapshot below (fitting/fetch_odds.py): Betfair + William Hill (the-odds-api
# eu), DraftKings + BetRivers (the-odds-api us) and Kalshi (its own public API).
# The old frozen bet365 line (observed 28 May 2026, top ~16) was dropped once
# the tournament started — it isn't on any feed we can refresh, so leaving it
# would dilute the bookmaker leg with pre-tournament priors. To add a book,
# either extend ALLOWED_BOOKS in fetch_odds or drop {team: decimal_odds} here.
_DECIMAL_BOOKS: dict[str, dict[str, float]] = {}


def _decimal_to_american(d: float) -> int:
    """Decimal (European) odds -> American moneyline int."""
    return round((d - 1) * 100) if d >= 2.0 else round(-100 / (d - 1))


# Merge the baked odds snapshot from the offline fetcher (fitting/fetch_odds.py,
# the-odds-api: Betfair exchange + William Hill). Keys already use our English
# names. Committed artifact — the runtime never calls the API.
_SNAPSHOT = os.path.join(os.path.dirname(__file__), "odds_snapshot.json")
try:
    with open(_SNAPSHOT, encoding="utf-8") as _f:
        for _bk, _od in json.load(_f).items():
            _DECIMAL_BOOKS.setdefault(_bk, {}).update(
                {_t: float(_v) for _t, _v in _od.items()})
except FileNotFoundError:
    pass


for _book, _odds in _DECIMAL_BOOKS.items():
    for _team_en, _dec in _odds.items():
        BOOKMAKER_ODDS.setdefault(_team_en, {})[_book] = _decimal_to_american(_dec)

# Notable-expert / model predictions, collected mid-April–27 May 2026 (see
# sources in research notes). semifinalists lists exclude the winner/finalist
# (which are scored separately) to avoid double counting.
EXPERT_PICKS: list[dict] = [
    {"name": "Gary Lineker", "outlet": "BBC", "winner": "Spain", "finalist": None, "semifinalists": []},
    {"name": "Micah Richards", "outlet": "BBC", "winner": "Spain", "finalist": None, "semifinalists": []},
    {"name": "Jamie Carragher", "outlet": "Sky/CBS", "winner": "France", "finalist": "Portugal", "semifinalists": ["Spain", "England"]},
    {"name": "Thierry Henry", "outlet": "CBS", "winner": "France", "finalist": None, "semifinalists": []},
    {"name": "Peter Crouch", "outlet": "Podcast", "winner": "England", "finalist": None, "semifinalists": []},
    {"name": "Opta supercomputer", "outlet": "Opta Analyst", "winner": "Spain", "finalist": "France", "semifinalists": ["England", "Argentina"]},
    {"name": "NerdyTips AI", "outlet": "NerdyTips", "winner": "France", "finalist": None, "semifinalists": ["Spain", "England", "Argentina"]},
    {"name": "Paulina Vairo", "outlet": "RotoWire", "winner": "Portugal", "finalist": "France", "semifinalists": ["Spain", "Argentina"]},
    {"name": "Frank Monkhouse", "outlet": "Flashscore", "winner": "France", "finalist": None, "semifinalists": []},
    {"name": "Mark Andrews", "outlet": "MA Football Analysis", "winner": "France", "finalist": None, "semifinalists": []},
    {"name": "Mark Ogden", "outlet": "ESPN", "winner": "Spain", "finalist": None, "semifinalists": []},
    {"name": "James Olley", "outlet": "ESPN", "winner": "Spain", "finalist": None, "semifinalists": []},
    {"name": "Julien Laurens", "outlet": "ESPN", "winner": "England", "finalist": None, "semifinalists": []},
    {"name": "Gab Marcotti", "outlet": "ESPN", "winner": "England", "finalist": None, "semifinalists": []},
    {"name": "Bill Connelly", "outlet": "ESPN", "winner": "England", "finalist": None, "semifinalists": []},
    {"name": "Ryan O'Hanlon", "outlet": "ESPN", "winner": "France", "finalist": None, "semifinalists": []},
    {"name": "Rob Dawson", "outlet": "ESPN", "winner": "Argentina", "finalist": None, "semifinalists": []},
    {"name": "Alexi Lalas", "outlet": "Fox", "winner": None, "finalist": None, "semifinalists": ["France", "Spain", "Argentina", "Germany", "England"]},
    # Country-diverse picks added 2026-06-01 from web research; every entry is a
    # real, named source with a cited URL (see fitting/expert_sources.md). The
    # `country` tag = the media market the pundit was sourced from.
    {"name": "Lothar Matthäus", "outlet": "Sky/Sport Bild", "country": "Germany", "winner": "Spain", "finalist": "England", "semifinalists": ["Germany", "Argentina"]},
    {"name": "Joachim Klement", "outlet": "Econometric model (SBS/CNN)", "country": "Germany", "winner": "Netherlands", "finalist": "Portugal", "semifinalists": ["Spain"]},
    {"name": "Rafael van der Vaart", "outlet": "Ziggo Sport", "country": "Netherlands", "winner": None, "finalist": None, "semifinalists": ["Netherlands"]},
    {"name": "Michal Trávníček", "outlet": "BetArena.cz", "country": "Czechia", "winner": "Germany", "finalist": None, "semifinalists": []},
    {"name": "Michal Konvalina", "outlet": "BetArena.cz", "country": "Czechia", "winner": "France", "finalist": None, "semifinalists": []},
    {"name": "Jan Keňo", "outlet": "BetArena.cz", "country": "Czechia", "winner": "Spain", "finalist": None, "semifinalists": []},
    {"name": "Petr Luzar", "outlet": "BetArena.cz", "country": "Czechia", "winner": "Spain", "finalist": None, "semifinalists": []},
    {"name": "El Hadji Diouf", "outlet": "Le Soleil", "country": "Senegal", "winner": "Spain", "finalist": None, "semifinalists": []},
    {"name": "Javier \"Chicharito\" Hernández", "outlet": "Fox Sports (via AP)", "country": "Mexico", "winner": "England", "finalist": None, "semifinalists": []},
    {"name": "Hugo Sánchez", "outlet": "Uno TV", "country": "Mexico", "winner": "Spain", "finalist": None, "semifinalists": ["Argentina", "France"]},
    {"name": "Stu Holden", "outlet": "Fox Sports", "country": "USA", "winner": "France", "finalist": None, "semifinalists": []},
    {"name": "Carli Lloyd", "outlet": "Fox Sports", "country": "USA", "winner": "France", "finalist": None, "semifinalists": []},
    {"name": "Rob Stone", "outlet": "Fox Sports", "country": "USA", "winner": "Spain", "finalist": None, "semifinalists": []},
]

# team(EN) -> FIFA world ranking position (display only)
FIFA_RANK: dict[str, int] = {}

# Weights for picks when aggregating expert signal.
_EXPERT_W = {"winner": 1.0, "finalist": 0.5, "semifinalist": 0.25}


def american_to_prob(odds: int) -> float:
    """American moneyline odds -> implied probability (with vig)."""
    if odds < 0:
        return -odds / (-odds + 100.0)
    return 100.0 / (odds + 100.0)


def _devig_shin(raw: dict[str, float]) -> dict[str, float]:
    """Shin (1992) de-vig: solve z so the implied probs sum to 1. Unlike plain
    normalisation it corrects the favourite-longshot bias (shifts mass toward
    favourites), which matters in a long-tailed many-runner title market."""
    teams = list(raw)
    r = [raw[t] for t in teams]
    V = sum(r)
    if V <= 0:
        return {}

    def psum(z):
        return sum((math.sqrt(z * z + 4 * (1 - z) * ri * ri / V) - z) / (2 * (1 - z))
                   for ri in r)
    lo, hi = 0.0, 0.95
    for _ in range(80):                # sum p decreases as z rises -> bisect
        mid = (lo + hi) / 2
        if psum(mid) > 1:
            lo = mid
        else:
            hi = mid
    z = (lo + hi) / 2
    return {t: (math.sqrt(z * z + 4 * (1 - z) * ri * ri / V) - z) / (2 * (1 - z))
            for t, ri in zip(teams, r)}


def bookmaker_probs() -> dict[str, float]:
    """De-vigged (Shin's method) implied title probability per team (SV keys)."""
    if not BOOKMAKER_ODDS:
        return {}
    raw: dict[str, float] = {}
    for team_en, bybook in BOOKMAKER_ODDS.items():
        sv = to_sv(team_en)
        if sv is None or not bybook:
            continue
        probs = [american_to_prob(o) for o in bybook.values()]
        raw[sv] = sum(probs) / len(probs)   # avg raw implied prob across books
    return _devig_shin(raw)


def expert_probs() -> dict[str, float]:
    """Aggregate expert picks into a normalized weight per team (SV keys)."""
    if not EXPERT_PICKS:
        return {}
    score: dict[str, float] = {}
    for pick in EXPERT_PICKS:
        for sv in [to_sv(pick.get("winner", ""))]:
            if sv:
                score[sv] = score.get(sv, 0.0) + _EXPERT_W["winner"]
        sv = to_sv(pick.get("finalist", ""))
        if sv:
            score[sv] = score.get(sv, 0.0) + _EXPERT_W["finalist"]
        for s in pick.get("semifinalists", []) or []:
            sv = to_sv(s)
            if sv:
                score[sv] = score.get(sv, 0.0) + _EXPERT_W["semifinalist"]
    total = sum(score.values())
    if total <= 0:
        return {}
    return {t: s / total for t, s in score.items()}


def _rank_onto_fifa(order: list[str], ladder: list[float]) -> dict[str, float]:
    """Map a best->worst team ordering onto the sorted FIFA rating ladder, so
    the resulting ratings share the FIFA scale (same min/max/spread)."""
    return {team: ladder[i] for i, team in enumerate(order)}


def _zscore(d: dict[str, float]) -> dict[str, float]:
    """Standardize values to mean 0, sd 1 (sd=1 if degenerate)."""
    vals = list(d.values())
    if not vals:
        return {}
    m = sum(vals) / len(vals)
    sd = (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5 or 1.0
    return {k: (v - m) / sd for k, v in d.items()}


def blended_ratings(fifa_rating: dict[str, int],
                    weights=BLEND_W) -> dict[str, float]:
    """Effective rating per team: a weighted average of STANDARDIZED signals on
    the log-odds (rating) scale, rescaled to the FIFA-points spread so the goal
    model needs no recalibration. ``weights`` is (rankings, book, expert).

      * rankings - pure Elo. (FIFA dropped: M6 and the blend_grid backtest show
                   it adds ~0 RPS; reintroduce only as an explicit weighted leg.)
      * book     - de-vigged (Shin) bookmaker title prob -> logit.
      * expert   - aggregated expert pick weight -> logit.

    Each signal is z-scored across the field, then teams are blended over the
    signals they actually have (weights renormalized). MAGNITUDE IS PRESERVED:
    no rank ladder, so a clear #1 stays clearly ahead of a close #2. Z-scoring
    logit(title-odds) also cancels the knockout "compression" (logit(title) ~
    k*strength), so no de-compression constant is needed. The composite is
    mapped to the FIFA mean/sd, keeping the title-odds concentration the goal
    model was calibrated to while fixing the within-field spacing.
    """
    teams = list(fifa_rating)
    ladder = [float(r) for r in fifa_rating.values()]
    lmean = sum(ladder) / len(ladder)
    lsd = (sum((x - lmean) ** 2 for x in ladder) / len(ladder)) ** 0.5 or 1.0
    w_rank, w_book, w_exp = weights

    # rankings leg = pure Elo (fall back to FIFA points only if no Elo data)
    if ELO_RATING and all(t in ELO_RATING for t in teams):
        z_rank = _zscore({t: float(ELO_RATING[t]) for t in teams})
    else:
        z_rank = _zscore({t: float(fifa_rating[t]) for t in teams})

    bp = bookmaker_probs()
    z_book = _zscore({t: math.log(bp[t] / (1 - bp[t]))
                      for t in teams if 0 < bp.get(t, 0) < 1})
    # Experts are sparse: being named is positive evidence, absence is neutral.
    # z-score the raw pick weight over the WHOLE field (unnamed = 0) so a
    # named-but-low team isn't pushed BELOW unnamed teams (which a logit over
    # only-named teams perversely did).
    ep = expert_probs()
    z_exp = _zscore({t: ep.get(t, 0.0) for t in teams})

    # weighted log-pool over the signals each team has (renormalized)
    comp = {}
    for t in teams:
        num, den = w_rank * z_rank[t], w_rank
        if t in z_book:
            num += w_book * z_book[t]; den += w_book
        if t in z_exp:
            num += w_exp * z_exp[t]; den += w_exp
        comp[t] = num / den

    # rescale composite to the FIFA-points spread (preserves goal-model scale)
    z = _zscore(comp)
    return {t: lmean + lsd * z[t] for t in teams}


def _blended_ratings_ladder(fifa_rating: dict[str, int],
                            weights=BLEND_W) -> dict[str, float]:
    """OLD rank-ladder blend, kept for A/B comparison only (do not ship). Maps
    each signal's rank onto the FIFA-points ladder, discarding magnitude."""
    teams = list(fifa_rating)
    ladder = sorted((float(r) for r in fifa_rating.values()), reverse=True)
    bp = bookmaker_probs()
    ep = expert_probs()
    fifa_order = sorted(teams, key=lambda t: fifa_rating[t], reverse=True)
    r_fifa = _rank_onto_fifa(fifa_order, ladder)
    if ELO_RATING and all(t in ELO_RATING for t in teams):
        w_elo, w_fifa = RANK_W
        elo_order = sorted(teams, key=lambda t: (ELO_RATING[t], fifa_rating[t]),
                           reverse=True)
        r_elo = _rank_onto_fifa(elo_order, ladder)
        r_rank = {t: (w_elo * r_elo[t] + w_fifa * r_fifa[t]) / (w_elo + w_fifa)
                  for t in teams}
    else:
        r_rank = r_fifa
    book_order = sorted(teams, key=lambda t: (bp.get(t, 0.0), fifa_rating[t]),
                        reverse=True)
    exp_order = sorted(teams, key=lambda t: (ep.get(t, 0.0), bp.get(t, 0.0),
                                             fifa_rating[t]), reverse=True)
    r_book = _rank_onto_fifa(book_order, ladder)
    r_exp = _rank_onto_fifa(exp_order, ladder)
    wr, wb, we = weights
    wsum = wr + wb + we
    return {t: (wr * r_rank[t] + wb * r_book[t] + we * r_exp[t]) / wsum
            for t in teams}


def expert_mentions() -> dict[str, int]:
    """Count of experts naming a team anywhere (winner/finalist/semifinalist)."""
    counts: dict[str, int] = {}
    for pick in EXPERT_PICKS:
        named = set()
        for key in ("winner", "finalist"):
            sv = to_sv(pick.get(key) or "")
            if sv:
                named.add(sv)
        for s in pick.get("semifinalists", []) or []:
            sv = to_sv(s)
            if sv:
                named.add(sv)
        for sv in named:
            counts[sv] = counts.get(sv, 0) + 1
    return counts


def avg_american_odds(team_en: str):
    """Average American odds across books for a team (for display)."""
    by = BOOKMAKER_ODDS.get(team_en)
    if not by:
        return None
    return round(sum(by.values()) / len(by))


def experts_for_team(team_en: str) -> list[dict]:
    """Experts who named this team, with their role (winner/finalist/semi)."""
    out = []
    for pick in EXPERT_PICKS:
        role = None
        if pick.get("winner") == team_en:
            role = "winner"
        elif pick.get("finalist") == team_en:
            role = "finalist"
        elif team_en in (pick.get("semifinalists") or []):
            role = "semifinalist"
        if role:
            out.append({"name": pick["name"], "outlet": pick.get("outlet"),
                        "role": role})
    return out


def team_signals(fifa_rating: dict[str, int]) -> dict[str, dict]:
    """Per-team breakdown for the UI (book/expert probs, fifa rank, blended)."""
    bp = bookmaker_probs()
    ep = expert_probs()
    em = expert_mentions()
    blended = blended_ratings(fifa_rating)
    sv_en = {sv: en for en, sv in NAME_EN_SV.items()}
    by_points = sorted(fifa_rating, key=lambda t: fifa_rating[t], reverse=True)
    rank_by_points = {t: i + 1 for i, t in enumerate(by_points)}
    rank_sv = {to_sv(en): r for en, r in FIFA_RANK.items() if to_sv(en)}
    out = {}
    for t in fifa_rating:
        en = sv_en.get(t, t)
        nbooks = len(BOOKMAKER_ODDS.get(en, {}))
        out[t] = {
            "name_en": en,
            "fifa_rating": fifa_rating[t],
            "fifa_world_rank": rank_sv.get(t),           # may be None
            "fifa_field_rank": rank_by_points[t],         # 1..48 within field
            "book_prob": bp.get(t),                       # may be None
            "book_odds_avg": avg_american_odds(en),       # American, may be None
            "book_odds": BOOKMAKER_ODDS.get(en, {}),      # per-book American
            "book_count": nbooks,
            "expert_prob": ep.get(t),                     # may be None
            "expert_mentions": em.get(t, 0),
            "experts": experts_for_team(en),              # who named them
            "elo": ELO_RATING.get(t),
            "effective_rating": round(blended[t], 1),
        }
    return out


def model_meta() -> dict:
    """Summary of the external data driving the blend (for the UI footer)."""
    books = sorted({b for by in BOOKMAKER_ODDS.values() for b in by})
    return {
        "weights": {"rankings": 0.475, "bookmaker": 0.475, "expert": 0.05},
        "books": books,
        "num_experts": len(EXPERT_PICKS),
        "experts": [{"name": p["name"], "outlet": p.get("outlet"),
                     "winner": p.get("winner")} for p in EXPERT_PICKS],
    }
