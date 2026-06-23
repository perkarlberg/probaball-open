# Probaball — World Cup 2026 forecast

**Live: https://probaball.online**

Probaball is a free data-science simulation of the 2026 FIFA World Cup. It plays
the whole 48-team tournament out tens of thousands of times (Monte Carlo) and
reports each team's probability of winning the title, reaching every knockout
round, and finishing in each group position. Visitors can fix the outcome of
specific matches ("conviction games") and run their own simulation, in six
languages. Not affiliated with or endorsed by FIFA.

---

## The model (v2)

Each team's **effective rating** is a weighted blend of three independent
signals (think "poll of polls" for football), each mapped onto a common scale by
rank/quantile matching:

| Bucket | Weight | What it is |
|---|---:|---|
| **Rankings** | 40% | **Elo** (0.85) computed walk-forward from ~50k historical internationals, + FIFA points (0.15, a light anchor) |
| **Bookmakers** | 40% | De-vigged title odds averaged across bet365, DraftKings, FanDuel, BetMGM, Kalshi |
| **Experts** | 20% | 18 named pundits + statistical models (ESPN panel, Lineker, Carragher, Opta, …) |

A match is a **bivariate Poisson** goal model driven by the rating gap, with a
**Dixon–Coles** low-score correction (ρ=-0.06, fixes the draw bias), a host edge
for USA/Mexico/Canada in the group stage and a reduced one in the knockouts.
Qualification uses the real 8-best-thirds rule, and the knockout stage uses
**FIFA's official 2026 R32 bracket + tree** (no balanced approximation).

Every modelling choice is judged by **out-of-sample Ranked Probability Score
(RPS)** on a backtest of historical international results — not by whether it
looks sophisticated. See `IMPROVEMENTS-05-31.md` (design spec) and `PLAN-v2.md`
(execution log).

### Tested model improvements — qualified vs. disqualified

The backtest harness (`backend/backtest/`) is the referee. What it kept and cut:

| Change | Verdict | Evidence |
|---|---|---|
| Walk-forward **Elo** as the rankings core | ✅ kept | Beats a naïve base rate (RPS 0.168 vs 0.228); the validated baseline |
| Elo **home advantage = 85** | ✅ kept | RPS 0.1727 → 0.1721 (plateau ~85–100) |
| **Dixon–Coles** low-score correction | ✅ kept | Small RPS gain + clearer Brier/log-loss; draw rate 25.9% → 27.0% |
| **40/40/20** blend (rankings/odds/expert) | ✅ kept | Spec prior; markets are the strongest single signal (odds/expert not match-RPS-tunable) |
| **Official FIFA 2026 bracket** | ✅ kept | Realistic paths; old balanced bracket over-separated top seeds |
| **Knockout host edge** (reduced) | ✅ kept | Modest, realistic lift to host deep runs |
| **FIFA ranking** as a rankings signal | ❌ disqualified | Adds *no* value beyond Elo; marginal coefficient negative, RPS worse → down-weighted to a 0.15 anchor (M6) |
| **Attack/defence (Maher) goal model** | ⚠️ measured, not integrated | Beats `elo_dc` overall — but the edge is its *overall* ratings (already in the blend, and the blend has the market too); the att/def **style** adds ~0 RPS (M4.2/M7) |
| Rescaling effective ratings to the **Elo scale** | ❌ rejected | Over-concentrated the title odds (Spain 28% vs market ~18%); kept ratings market-calibrated |
| **Squad value / xG / latent tournament-form** | ⏭️ skipped | Fragile/sparse data or magnitude not backtest-validatable (M8) |

The two disqualifications (FIFA, att/def style) are the harness doing its job.

---

## Architecture

Two tiers, so the heavy work never touches the free-tier runtime:

- **Offline fitting** (`backend/fitting/`, run locally): compute Elo from the
  historical dataset → `elo_ratings.json` (committed, shipped in the image).
- **Runtime** — **FastAPI on Cloud Run** (scales to zero): loads the baked
  ratings + market/expert data and runs the Monte Carlo. Live reruns are fixed
  at N=1000 (~2s); the canonical snapshot is N=50,000.
- **Firestore** — dated canonical snapshots + a capped (≤1000) log of parameter
  experiments (parameters only, no run outcomes).
- **Firebase Hosting** — React + Vite SPA, prerendered to static HTML per route
  (`/`, `/lag/<slug>`, `/grupp/<x>`) so search engines and AI crawlers get real
  content. Six languages (sv/en/es/fr/pt/de), browser-locale detected.

### Repo layout
```
backend/
  engine.py        Monte Carlo engine (match model, bracket, simulate)
  model_data.py    blend: Elo + bookmaker + expert -> effective ratings
  app.py           FastAPI: /canonical /simulate /sample-bracket /refresh /meta
  store.py         Firestore (prod) / local JSON (dev)
  elo_ratings.json baked Elo (from fitting/build_elo.py)
  fitting/         offline: build_elo.py
  backtest/        RPS/Brier/log-loss harness, Elo, Maher, comparisons
frontend/          React + Vite SPA; prerender.py emits static per-route HTML
deploy.sh          build + prerender + deploy (frontend | backend | reseed | all)
deploy_hosting.py  Firebase Hosting deploy via REST (org policy blocks SA keys)
PLAN-v2.md         v2 execution log;  IMPROVEMENTS-05-31.md  design spec
```

---

## Develop & deploy

**Local:**
```bash
# backend (no GOOGLE_CLOUD_PROJECT -> local JSON store)
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
ADMIN_TOKEN=dev uvicorn app:app --reload --port 8080
curl -X POST -H "X-Admin-Token: dev" localhost:8080/api/refresh   # seed canonical
cd ../frontend && npm install && npm run dev                      # proxies /api -> :8080
```

**Backtest** (the referee for any model change):
```bash
cd backend
python3 -m backtest.fetch_data     # download historical results (gitignored)
python3 -m backtest.run            # baseline RPS (elo_dc vs naive)
python3 -m backtest.compare_ad     # attack/defence vs elo_dc
python3 -m backtest.compare_fifa   # does FIFA add to Elo? (no)
python3 -m fitting.build_elo       # refresh elo_ratings.json
```

**Deploy** (GCP project `probaball`; run from repo root, **foreground**):
```bash
./deploy.sh all        # backend -> reseed canonical -> frontend
./deploy.sh frontend   # build + prerender + Firebase Hosting only
./deploy.sh reseed     # recompute canonical, then frontend
```
After changing ratings/data, reseed so the canonical snapshot matches the model.

---

## Data sources & caveats
- Historical results: `martj42/international_results` (CC0, ~49k matches).
- FIFA ranking history (Dato-Futbol) — used only to *test* the FIFA weight.
- Bookmaker odds (late May 2026) + 18 expert picks — current snapshot, hard-coded.
- **Limit:** there is no historical per-international-match odds archive, so the
  bookmaker/expert weighting is calibrated to the live title market, not match
  RPS. Elo and the goal model *are* RPS-validated.

## Backlog / open questions
- **Home advantage on neutral-venue group matches (verify).** Match win
  probabilities are presented neutrally (team-vs-team, no "home/away"), but the
  engine carries `home_adv=85`. Confirm it is *not* applied to neutral-venue WC
  group games (only to genuine host-nation matches via `ko_host_adv`/host logic);
  otherwise the per-match probabilities are biased toward whichever team is
  arbitrarily listed "home", which matters for a product whose pitch is *correct*
  probabilities. Model question, not SEO — gate any change on the RPS backtest.
- **Head-to-head on match pages (SEO P3).** Every competitor (Forebet, FootyStats,
  AiScore, 11v11) surfaces an H2H record + last-meetings table, and Google pulls
  the all-time record into the answer box; we don't have it. We already hold ~49k
  historical internationals (the Elo build data), so per-fixture H2H can be
  computed offline and baked. Needs a data-pipeline step, not just a prerender
  copy change.
- **Knockout match pages (post-June 27).** Per-match knockout prediction pages
  (R32→Final) become buildable once group standings lock and pairings are known;
  needs the backend to emit knockout fixtures + per-fixture probabilities into the
  canonical (like `group_matches`), then prerender generates the pages.
