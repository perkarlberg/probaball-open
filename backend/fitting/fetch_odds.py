#!/usr/bin/env python3
"""
Offline odds fetcher (the-odds-api.com) -> backend/odds_snapshot.json.

Bakes a static artifact in the offline tier; the runtime never calls the API.
Run manually (or on a schedule) to refresh bookmaker odds, then reseed.

COST DISCIPLINE: the-odds-api charges 1 credit per region per market. This
script makes ONE credit-costing call per run covering TWO regions (regions=
eu,us, markets=outrights) = 2 credits. The /v4/sports lookup is free, and the
Kalshi pull (below) is its own free public API. With a 500 req/month plan that
supports daily refreshes (~60 credits/mo) with huge headroom. It prints
x-requests-remaining so you can watch the budget.

Live books we get (all refreshed every run, no frozen priors):
  * the-odds-api eu = {Betfair, William Hill}, us = {DraftKings, BetRivers}
  * Kalshi  — full 48-team board, its own public JSON API (KXMENWORLDCUP)
  * FanDuel — FOX Sports' FanDuel-attributed champion-odds page (HTML scrape)
the-odds-api carries only those 4 sportsbooks for this market (confirmed live).
BetMGM and bet365 stay OUT: BetMGM only appears on mixed-column aggregators
(can't attribute a column to it with confidence), and bet365's own board plus
every aggregator carrying it are bot-blocked (403). We don't bake odds we can't
attribute to a named book — see the research notes in this module's history.

Usage:
  ODDS_API_KEY=... python3 -m fitting.fetch_odds            # write snapshot
  ODDS_API_KEY=... python3 -m fitting.fetch_odds --dry-run  # print, don't write

Key lives in the environment only — never commit it or ship it to Cloud Run.
"""
import json
import os
import sys
import urllib.request

API = "https://api.the-odds-api.com/v4"
REGIONS = "eu,us"  # 2 credits/call; eu={Betfair,William Hill}, us={DraftKings,BetRivers}
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "odds_snapshot.json")

# Kalshi public market-data API (no auth for GET). The 2026 men's World Cup
# winner market is one binary market per team under this event; prices are the
# yes-side implied probability in dollars (0.185 = 18.5%).
KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_SERIES = "KXMENWORLDCUP"

# FanDuel isn't on the-odds-api for this market, but FOX Sports publishes a
# FanDuel-attributed WC champion-odds board as server-rendered HTML, refreshed
# daily through the tournament. We scrape it best-effort (graceful on layout
# change). (BetMGM/bet365 have no comparably clean, attributable source: BetMGM
# only shows on mixed-column aggregators, bet365's board + every aggregator
# carrying it are bot-blocked — so they stay out rather than be misattributed.)
FANDUEL_URL = "https://www.foxsports.com/stories/soccer/world-cup-2026-champion-odds"

# English team names as they appear on US odds pages (longest-first so multi-word
# names match before substrings); mapped to our keys via NAME_ALIASES.
_FOX_TEAMS = [
    "Bosnia and Herzegovina", "United States", "South Korea", "South Africa",
    "Saudi Arabia", "New Zealand", "Ivory Coast", "Cape Verde", "DR Congo",
    "Netherlands", "Switzerland", "Uzbekistan", "Argentina", "Australia",
    "Paraguay", "Scotland", "Portugal", "Colombia", "Czechia", "Senegal",
    "Belgium", "Croatia", "Ecuador", "Germany", "Morocco", "Tunisia", "England",
    "Algeria", "Austria", "Curacao", "Denmark", "Jordan", "Mexico", "Norway",
    "Panama", "Sweden", "Turkey", "Canada", "Brazil", "Egypt", "France", "Ghana",
    "Japan", "Qatar", "Spain", "Haiti", "Iran", "Iraq", "Mali", "Peru",
    "Uruguay", "Wales",
]

# the-odds-api team name -> our English key (only the ones that differ).
NAME_ALIASES = {
    "United States": "USA", "USA": "USA",
    "Korea Republic": "South Korea", "Republic of Korea": "South Korea",
    "South Korea": "South Korea",
    "Czech Republic": "Czechia",
    "Cote D'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast",
    "Côte d'Ivoire": "Ivory Coast", "Ivory Coast": "Ivory Coast",
    "Turkiye": "Turkey", "Türkiye": "Turkey",
    "Congo DR": "DR Congo", "DR Congo": "DR Congo",
    "Democratic Republic of Congo": "DR Congo",
    "Cape Verde Islands": "Cape Verde", "Curaçao": "Curacao",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Bosnia and Herzegovina": "Bosnia and Herzegovina",
}

# Reputable books to keep (the-odds-api titles); broadens the US-centric set.
ALLOWED_BOOKS = {
    "bet365", "Unibet", "Betsson", "Pinnacle", "William Hill", "1xBet",
    "Betfair", "Betway", "Marathon Bet", "Betclic", "Coolbet", "NordicBet",
    "Tipico", "LeoVegas", "Nordic Bet", "Betfair Sportsbook",
    "DraftKings", "BetRivers", "FanDuel", "BetMGM",  # us region
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r), dict(r.headers)


def _kalshi_book():
    """Pull Kalshi's live 2026 WC winner board -> {our_key: decimal_odds}.

    Free public endpoint, no credit cost. Each team is a binary market; the
    yes-side mid (or last trade) is the implied title probability, which we
    invert to decimal odds so it merges with the bookmaker decimals."""
    url = (f"{KALSHI_API}/markets?series_ticker={KALSHI_SERIES}"
           f"&status=open&limit=100")
    try:
        data, _ = _get(url)
    except Exception as e:  # noqa: BLE001 — Kalshi is best-effort, never fatal
        print(f"  Kalshi: skipped ({e})")
        return {}

    def _f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    out = {}
    for m in data.get("markets", []):
        name = m.get("yes_sub_title") or m.get("no_sub_title")
        if not name:
            continue
        yb, ya = _f(m.get("yes_bid_dollars")), _f(m.get("yes_ask_dollars"))
        nb, na = _f(m.get("no_bid_dollars")), _f(m.get("no_ask_dollars"))
        last = _f(m.get("last_price_dollars"))
        if yb and ya:
            p = (yb + ya) / 2.0
        elif nb and na:
            p = 1.0 - (nb + na) / 2.0
        else:
            p = last
        if not p or p <= 0:
            continue
        our = NAME_ALIASES.get(name, name)
        out[our] = round(1.0 / p, 2)  # implied prob -> decimal odds
    print(f"  Kalshi: {len(out)} teams")
    return out


def _american_to_decimal(a: int) -> float:
    """American moneyline -> decimal odds."""
    return round(1.0 + (a / 100.0 if a > 0 else 100.0 / -a), 2)


def _fanduel_book():
    """Scrape FanDuel's WC-winner board from FOX Sports -> {our_key: decimal}.

    Best-effort: returns {} on any failure (incl. the page dropping its FanDuel
    attribution) so the snapshot still has the other books. FOX renders the
    table server-side as 'Team +odds' prose."""
    import re
    req = urllib.request.Request(FANDUEL_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — best-effort, never fatal
        print(f"  FanDuel (FOX): skipped ({e})")
        return {}
    if "FanDuel" not in html:
        print("  FanDuel (FOX): skipped (page no longer FanDuel-attributed)")
        return {}
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    out = {}
    for tm in _FOX_TEAMS:
        # Table rows read "Team: +410"; tolerate the colon/space separator so we
        # skip prose mentions (e.g. the "France Favored" headline) and match the
        # priced row. [:\s]{0,3} won't bridge into another word.
        m = re.search(re.escape(tm) + r"[:\s]{0,3}(\+\d{2,5})", plain)
        if not m:
            continue
        our = NAME_ALIASES.get(tm, tm)
        out.setdefault(our, _american_to_decimal(int(m.group(1))))
    print(f"  FanDuel (FOX): {len(out)} teams")
    return out


def main():
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        sys.exit("Set ODDS_API_KEY in the environment.")
    dry = "--dry-run" in sys.argv

    # 1. Find the WC winner sport key (free, no credit cost).
    sports, _ = _get(f"{API}/sports?apiKey={key}&all=true")
    keys = [s["key"] for s in sports
            if "world_cup_winner" in s["key"] or
            ("fifa_world_cup" in s["key"] and "winner" in s["key"])]
    if not keys:
        print("Active sport keys mentioning world cup:")
        for s in sports:
            if "world_cup" in s["key"]:
                print(" ", s["key"], "-", s.get("title"), "active" if s.get("active") else "INACTIVE")
        sys.exit("Could not find a 'world_cup_winner' sport key — inspect the list above.")
    sport = keys[0]
    print(f"sport key: {sport}")

    # 2. Outright winner odds, ONE region = 1 credit.
    data, hdr = _get(f"{API}/sports/{sport}/odds?apiKey={key}"
                     f"&regions={REGIONS}&markets=outrights&oddsFormat=decimal")
    print(f"credits: used={hdr.get('x-requests-used')} "
          f"remaining={hdr.get('x-requests-remaining')}")

    # 3. Parse: {book_title: {our_key: decimal}}. data is a list (usually 1 event).
    books, unmapped = {}, set()
    for event in data:
        for bk in event.get("bookmakers", []):
            title = bk.get("title", "")
            if title not in ALLOWED_BOOKS:
                continue
            for mk in bk.get("markets", []):
                if mk.get("key") != "outrights":
                    continue
                for oc in mk.get("outcomes", []):
                    nm = oc.get("name", "")
                    our = NAME_ALIASES.get(nm, nm)
                    price = oc.get("price")
                    if not price:
                        continue
                    books.setdefault(title, {})[our] = round(float(price), 2)

    # 4. Free supplementary boards (no credit cost): Kalshi (full 48-team API)
    #    and FanDuel (FOX Sports HTML). Both best-effort — failures don't block.
    kalshi = _kalshi_book()
    if kalshi:
        books["Kalshi"] = kalshi
    fanduel = _fanduel_book()
    if fanduel:
        books["FanDuel"] = fanduel

    # Report coverage so name mismatches surface.
    all_titles = sorted({b.get("title", "") for e in data for b in e.get("bookmakers", [])})
    print(f"books available (the-odds-api eu,us): {all_titles}")
    print(f"books kept ({len(books)}): {sorted(books)}")
    for title, odds in sorted(books.items()):
        print(f"  {title}: {len(odds)} teams")

    if dry:
        print("\n--dry-run: not writing.")
        print(json.dumps(books, ensure_ascii=False, indent=2))
        return
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(books, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"\nwrote {os.path.abspath(OUT_PATH)}")


if __name__ == "__main__":
    main()
