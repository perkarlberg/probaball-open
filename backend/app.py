"""
VM 2026 simulation backend - FastAPI service for Cloud Run.

Endpoints
  GET  /api/health           liveness probe
  GET  /api/canonical        latest stored canonical result (read-only, public)
  POST /api/simulate         run 1000 sims with user params; persists the
                             parameter set only (capped); returns fresh results
  POST /api/sample-bracket   reroll one representative bracket for given params
  POST /api/refresh          admin: store the canonical snapshot (token-gated);
                             accepts a precomputed snapshot body (preferred:
                             computed locally) or simulates server-side if none
  GET  /api/meta             available snapshot dates + param-experiment count

The simulation N for live reruns is FIXED at 1000 (see project spec). The
canonical refresh uses a larger N for a tighter estimate.
"""

from __future__ import annotations

import json
import os
import random
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import engine
import store

LIVE_N = 1000                                   # fixed N for user reruns
CANONICAL_N = int(os.environ.get("CANONICAL_N", "50000"))
CANONICAL_SEED = 42                             # stable canonical across refreshes
# Tournament mode: from kickoff, the "Change" column rebases to a fixed
# pre-tournament snapshot instead of the 7-day rolling window.
TOURNAMENT_START = "2026-06-11"
TOURNAMENT_BASELINE = "2026-06-10"
# Bracket search budgets: the representative-bracket filter is strict, so it
# usually runs to the cap. Keep live snappy; let the canonical search longer.
LIVE_PODIUM_TRIES = int(os.environ.get("LIVE_PODIUM_TRIES", "6000"))
CANONICAL_PODIUM_TRIES = int(os.environ.get("CANONICAL_PODIUM_TRIES", "60000"))
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

app = FastAPI(title="VM 2026 Simulation API", version="1.0.0")

_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:4173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ForcedGame(BaseModel):
    a: str
    b: str
    winner: str


class ParamInput(BaseModel):
    goal_scale: float = Field(default=engine.DEFAULT_PARAMS.goal_scale)
    base_goals: float = Field(default=engine.DEFAULT_PARAMS.base_goals)
    home_adv: float = Field(default=engine.DEFAULT_PARAMS.home_adv)
    rho: float = Field(default=engine.DEFAULT_PARAMS.rho)
    forced: Optional[List[ForcedGame]] = None


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/meta")
def meta():
    s = store.get_store()
    return {
        "snapshot_dates": s.list_canonical_dates(),
        "param_experiment_count": s.param_experiment_count(),
        "param_cap": store.PARAM_CAP,
        "live_n": LIVE_N,
        "default_params": engine.asdict(engine.DEFAULT_PARAMS),
        "param_bounds": engine.PARAM_BOUNDS,
    }


@app.get("/api/canonical")
def canonical():
    s = store.get_store()
    snap = s.get_latest_canonical()
    if snap is None:
        raise HTTPException(status_code=404,
                            detail="No canonical snapshot yet. Run /api/refresh.")
    return snap


@app.get("/api/snapshot/{snap_date}")
def snapshot(snap_date: str):
    snap = store.get_store().get_canonical(snap_date)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"No snapshot for {snap_date}")
    return snap


def _ranked(snap: dict) -> dict:
    """team -> (rank, team_obj), rank 1-based by champion probability."""
    teams = sorted(snap.get("teams", []), key=lambda t: -(t.get("champion") or 0))
    return {t["team"]: (i + 1, t) for i, t in enumerate(teams)}


@app.get("/api/trends")
def trends(frm: Optional[str] = None, to: Optional[str] = None):
    """Per-team movement between two dated snapshots (defaults: latest vs the
    snapshot before it). Powers 'Germany 8th->6th', 'England odds +X%' etc."""
    s = store.get_store()
    dates = s.list_canonical_dates()  # descending
    if not dates:
        raise HTTPException(status_code=404, detail="No snapshots yet.")
    to = to or dates[0]
    if frm is None:
        earlier = [d for d in dates if d < to]
        frm = earlier[0] if earlier else to
    a, b = s.get_canonical(frm), s.get_canonical(to)
    if a is None or b is None:
        raise HTTPException(status_code=404, detail="Snapshot date(s) not found.")
    ra, rb = _ranked(a), _ranked(b)
    rows = []
    for team, (rank_b, tb) in rb.items():
        if team not in ra:
            continue
        rank_a, ta = ra[team]
        ba, bb = ta.get("book_prob"), tb.get("book_prob")
        ea, eb = ta.get("elo"), tb.get("elo")
        ca, cb = ta.get("champion") or 0, tb.get("champion") or 0
        rows.append({
            "team": team, "name_en": tb.get("name_en", team),
            "rank_from": rank_a, "rank_to": rank_b, "rank_delta": rank_a - rank_b,
            "champion_from": ca, "champion_to": cb,
            "champion_delta": round(cb - ca, 4),
            "elo_from": ea, "elo_to": eb,
            "elo_delta": (round(eb - ea, 1) if ea is not None and eb is not None else None),
            "book_prob_from": ba, "book_prob_to": bb,
            "book_prob_pct": (round((bb - ba) / ba * 100, 1) if ba and bb else None),
        })
    rows.sort(key=lambda r: r["champion_delta"], reverse=True)
    return {"frm": frm, "to": to, "dates_available": dates, "teams": rows}


_HISTORY_CACHE: dict = {}


@app.get("/api/history")
def history():
    """Per-team championship-probability time series across every stored daily
    snapshot — powers the 'title race' charts. Cached in-process keyed by the
    snapshot date range (recomputed only when a new day lands)."""
    s = store.get_store()
    dates = sorted(s.list_canonical_dates())  # ascending
    if not dates:
        raise HTTPException(status_code=404, detail="No snapshots yet.")
    key = (dates[0], dates[-1], len(dates))
    if _HISTORY_CACHE.get("key") == key:
        return _HISTORY_CACHE["val"]
    series: dict = {}
    for dt in dates:
        snap = s.get_canonical(dt)
        if not snap:
            continue
        for t in snap.get("teams", []):
            e = series.setdefault(t["team"], {"name_en": t.get("name_en"), "vals": {}})
            e["vals"][dt] = round(t.get("champion") or 0.0, 4)
    teams = [{"team": k, "name_en": v["name_en"],
              "champion": [v["vals"].get(dt) for dt in dates]}
             for k, v in series.items()]
    teams.sort(key=lambda r: -(r["champion"][-1] or 0))
    out = {"dates": dates, "teams": teams}
    _HISTORY_CACHE.clear()
    _HISTORY_CACHE.update(key=key, val=out)
    return out


@app.post("/api/simulate")
def simulate(body: ParamInput):
    raw = body.model_dump()
    params = engine.coerce_params(raw)
    forced = engine.coerce_forced(raw.get("forced"))
    result = engine.run_simulation(LIVE_N, params, podium_tries=LIVE_PODIUM_TRIES,
                                   forced=forced)
    # Persist the parameter set + forced games only (no run outcomes), capped.
    experiment = dict(result["params"])
    if forced:
        experiment["forced"] = [{"a": k[0], "b": k[1], "winner": w}
                                for k, w in forced.items()]
    store.get_store().add_param_experiment(experiment)
    return result


class RerollInput(ParamInput):
    top: Optional[List[str]] = None


@app.post("/api/sample-bracket")
def reroll_bracket(body: RerollInput):
    raw = body.model_dump()
    params = engine.coerce_params(raw)
    forced = engine.coerce_forced(raw.get("forced"))
    ranked = body.top
    if not ranked or len(ranked) < 8:
        # No ranking supplied: derive it from a quick run.
        ranked = engine.run_simulation(LIVE_N, params, forced=forced)["top"]
    bracket, _ = engine.find_representative_bracket(params, ranked,
                                                    max_tries=LIVE_PODIUM_TRIES,
                                                    forced=forced)
    return bracket


def _attach_trend(result: dict, s) -> None:
    """Attach deltas to each team + a top-movers block, by comparing to a
    baseline snapshot. Pre-tournament: ~7-day rolling baseline. During the
    tournament: a FIXED pre-tournament baseline (TOURNAMENT_BASELINE) so the
    "Change" column reads "since the tournament started". No-op if there's no
    prior snapshot. teams are champion-sorted, so the list index is the rank."""
    def _complete(snap):
        ts = snap.get("teams") if snap else None
        return bool(ts) and ts[0].get("elo") is not None

    dates = s.list_canonical_dates()  # descending; today's not yet saved
    if not dates:
        return
    today = date.today().isoformat()
    if today >= TOURNAMENT_START:
        target = TOURNAMENT_BASELINE   # fixed: change since the tournament began
    else:
        target = (date.today() - timedelta(days=7)).isoformat()
    # Prefer the most recent complete snapshot on/before the target; until we
    # have that much history, fall back to the OLDEST complete snapshot (early
    # snapshots that predate the Elo field are skipped).
    base = base_date = None
    for d in [x for x in dates if x <= target]:
        snap = s.get_canonical(d)
        if _complete(snap):
            base, base_date = snap, d
            break
    if base is None:
        for d in reversed(dates):
            snap = s.get_canonical(d)
            if _complete(snap):
                base, base_date = snap, d
                break
    if base is None:
        return
    rb = _ranked(base)  # team -> (rank, obj)
    for rank_now, t in enumerate(result["teams"], start=1):
        prev = rb.get(t["team"])
        if not prev:
            continue
        rank_prev, tp = prev
        cprev, cnow = tp.get("champion") or 0, t.get("champion") or 0
        ep, en_ = tp.get("elo"), t.get("elo")
        bp, bn = tp.get("book_prob"), t.get("book_prob")
        t["rank_prev"] = rank_prev
        t["rank_delta"] = rank_prev - rank_now            # +ve = climbed
        t["champion_prev"] = cprev
        t["champion_delta"] = round(cnow - cprev, 5)       # percentage-point (as prob)
        t["champion_rel"] = round((cnow - cprev) / cprev * 100, 1) if cprev else None
        t["elo_prev"] = ep
        t["elo_delta"] = round(en_ - ep, 1) if ep is not None and en_ is not None else None
        t["book_prob_prev"] = bp
        t["book_prob_pct"] = round((bn - bp) / bp * 100, 1) if bp and bn else None

    def mover(t):
        return {"team": t["team"], "name_en": t.get("name_en"),
                "rank_from": t.get("rank_prev"), "rank_to": result["teams"].index(t) + 1,
                "champion_from": t.get("champion_prev"), "champion_to": t.get("champion"),
                "champion_rel": t.get("champion_rel")}
    top16 = [t for t in result["teams"][:16] if t.get("rank_delta") is not None]
    risers = [mover(t) for t in sorted(top16, key=lambda t: (-t["rank_delta"], -(t["champion_delta"] or 0))) if t["rank_delta"] > 0][:3]
    fallers = [mover(t) for t in sorted(top16, key=lambda t: (t["rank_delta"], (t["champion_delta"] or 0))) if t["rank_delta"] < 0][:3]
    result["trend"] = {"baseline_date": base_date, "risers": risers, "fallers": fallers}


@app.post("/api/refresh")
def refresh(snapshot: Optional[dict] = Body(default=None),
            x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # A precomputed snapshot may be uploaded (the 50k Monte Carlo is run locally
    # via reseed_local.py to keep that CPU burst off Cloud Run); otherwise fall
    # back to simulating here. Trend deltas + analysis are attached either way.
    if snapshot and snapshot.get("teams"):
        result, source = snapshot, "uploaded"
    else:
        random.seed(CANONICAL_SEED)
        result = engine.run_simulation(CANONICAL_N, podium_tries=CANONICAL_PODIUM_TRIES)
        source = "server"
    s = store.get_store()
    _attach_trend(result, s)
    # Editorial "movers" analysis (authored + translated each refresh; baked).
    try:
        with open(os.path.join(os.path.dirname(__file__), "analysis.json"),
                  encoding="utf-8") as f:
            result["analysis"] = json.load(f)
    except FileNotFoundError:
        pass
    today = date.today().isoformat()
    s.save_canonical(today, result)
    return {"saved": today, "n": result.get("n", CANONICAL_N),
            "champion_leader": result["teams"][0]["team"], "source": source}
