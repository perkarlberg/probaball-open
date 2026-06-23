# Probaball v2 — implementation plan

Companion to `IMPROVEMENTS-05-31.md` (the design spec). This is the execution
plan: how the spec lands in *this* codebase, in what order, and under what
constraints. Scope: **full v2 (M1–M8)**, built one measurable step at a time.

## Guiding rule (from the spec)
Nothing ships unless it lowers out-of-sample **Ranked Probability Score (RPS)**
on the backtest. Build the harness (M1) first; judge every later step by it.

## Architecture: offline fitting vs. runtime (the key adaptation)
The app runs on **Cloud Run (scale-to-zero, free tier)** with **live N=1000
reruns** that must stay ~sub-2s. So v2 is split in two:

- **Offline fitting pipeline** (`backend/fitting/`, run manually/locally): fetch
  historical data → compute Elo → fit attack/defence + Dixon–Coles (MLE, later
  PyMC/MCMC) → emit a static **`model_params.json`** (committed/snapshotted).
  Heavy deps (PyMC) live only here, never on Cloud Run.
- **Runtime engine** loads the baked params and runs the Monte Carlo (still
  light). Users keep tweaking high-level knobs; fitted attack/defence are fixed.

## Known data limit
The backtest scores **match W/D/L**. Elo is computable as-of-date, so it
rigorously validates the rankings + goal-model steps (M1, M2, M4, M5). But
**per-international-match bookmaker/expert odds history barely exists**, so the
40/40/20 bookmaker/expert weighting (M3, M6) is calibrated to the live title
market, *not* match-RPS-tuned. Documented, not hidden.

## What v1 already has
- Blended strength (FIFA + bookmaker + expert, equal 1/3, rank/quantile matched).
- Proportional de-vig of bookmaker odds.
- Monte Carlo scaffold, 8-best-thirds qualification, seeded RNG, CLI + per-stage
  output — all reused per spec §7.

## Milestones (each shippable, each gated by backtest RPS)
1. **M1 — Backtest harness.** Historical results dataset + RPS/Brier/log-loss +
   walk-forward Elo + runner. Report baseline RPS. *Offline. ← building now.*
2. **M2 — Elo + FIFA rankings bucket** (Elo 60 / FIFA 25 / squad 15 optional).
3. **M3 — Reweight blend to 40/40/20** (rankings / bookmaker / expert).
4. **M4 — Goal model rebuild**: attack/defence (MLE) + Dixon–Coles + time decay.
5. **M5 — Official FIFA 2026 knockout mapping** (replace balanced bracket).
6. **M6 — Expert bucket + grid-search the weights** on backtest.
7. **M7 — Bayesian hierarchical goal model** (PyMC, offline) w/ uncertainty.
8. **M8 — Refinements**: time-weighted xG, squad value, latent tournament-form
   draw, knockout host edge — keep each only if it lowers RPS.

## Data sources
| Source | Feeds | Status |
|---|---|---|
| martj42/international_results (CSV) | backtest + Elo + goal-model fit | ✅ fetched |
| Elo (computed from results) | rankings bucket | M1/M2 |
| FIFA ranking (have current) | rankings bucket | ✅ |
| Bookmaker odds (have current title) | market bucket | ✅ (live only) |
| Official 2026 bracket table | knockout mapping | research (M5) |
| Transfermarkt squad value | rankings (optional) | M8 |
| Int'l xG (FBref/StatsBomb) | time-weighted form | M8, sparse |

## Status log
- 2026-05-31: plan approved (full v2), M1 started; results dataset fetched.
- 2026-05-31: **M1 done.** `backend/backtest/` (fetch_data, elo, metrics, models,
  run). Walk-forward Elo + RPS/Brier/log-loss, fit on 2006–2014, test 2015→.
  **Baseline to beat** (test set, mean RPS): `elo_poisson` all **0.1727**,
  competitive **0.1678**, WC2018 0.2055, WC2022 0.2283 (vs naive base_rate
  0.2283 / 0.2319). Fitted goal_scale≈0.0053/Elo-pt, base_goals≈2.72.
  Run: `cd backend && python3 -m backtest.run`.
- 2026-05-31: **M2 done (code).** Elo is now the rankings core. Tuned Elo
  home_adv→85 on the backtest (RPS 0.1727→0.1721; plateau ~85–100, matches
  WF-Elo). `fitting/build_elo.py` computes current Elo for the 48 teams →
  committed `elo_ratings.json` (Spain 2229, Argentina 2183, France 2143…);
  added to Dockerfile COPY. `model_data.blended_ratings` rankings bucket =
  Elo 0.7 / FIFA 0.3 (RANK_W), replacing bare FIFA; `elo` exposed in team rows.
  Found historical FIFA archive (Dato-Futbol) for the M6 weight-tuning step;
  rigorous Elo+FIFA-weight backtest deferred to M6 (FIFA pre/post-2018 points
  regime). **Live deploy held** until the core (M3–M5) lands to avoid reseeding
  the canonical forecast repeatedly.
- 2026-05-31: **M3 done (code).** Overall blend reweighted to **40/40/20** (rankings/bookmaker/expert) via BLEND_W (spec §2.1). Live deploy still held.
- 2026-05-31: **M4 done (code).** Goal model validated + Dixon-Coles. Added DC
  low-score correction to the backtest (ρ fit on training → **ρ=-0.06**);
  elo_dc vs elo_poisson competitive RPS 0.1671 vs 0.1672, better Brier/logloss
  (calibration). Data-fit confirmed the hand-tuned goal constants are close
  (fit goal_scale 0.0052 / base 2.72 vs 0.0048 / 2.65) — kept market-calibrated
  (switching effective ratings to the Elo scale over-concentrated title odds, so
  Elo enters via the rankings bucket only, not by rescaling the ladder).
  Runtime: `engine.dc_sample` (accept-reject, ~11% reject, ~2s live reruns);
  Params.rho=-0.06. Live podium tries 12000→6000 to keep reruns snappy.
  **Attack/defence (per-team) deferred to M4.2** — measure vs elo_dc before
  integrating (Elo is hard to beat for internationals; ship only if RPS drops).
  Live deploy still held until M5.
- 2026-05-31: **M4.2 measured.** Maher/DC attack-defence model (`backtest/maher.py`,
  `backtest/compare_ad.py`, yearly refit) **beats elo_dc**: competitive RPS 0.1667
  vs 0.1671, WC2018 0.2029 vs 0.2063, WC2022 0.2120 vs 0.2286, better Brier/log-loss.
  Attack/defence validated; full integration (fuse att/def with market blend,
  blend-as-prior) **deferred to M7** — can't be match-RPS-validated, needs careful
  recalibration, so done as the dedicated goal-model layer not a rushed swap.
- 2026-05-31: **M5 done (code).** Replaced the balanced-bracket approximation with
  FIFA's official 2026 R32 layout (`_R32_LAYOUT`) + bracket tree (matches 73-104,
  Wikipedia knockout-stage page); winners/runners-up in their exact slots, 8 third
  slots tied to winners A,B,D,E,G,I,K,L (confirmed from Annex C). Thirds assigned by
  a constraint-respecting backtracking match (no team faces its own group's winner)
  — exact 495-row Annex C permutation among valid slots approximated (fragile to
  scrape; winners/runners/tree are exact). Validated: 0 dup/same-group errors over
  500 qualifications. Title odds shift slightly (favorites ~19%->17%: the old
  balanced bracket over-separated top seeds). _qualify now tracks qualifiers by
  group. **Core (M2-M5) complete — ready to reseed canonical + deploy.**
- 2026-05-31: **M6 done (code).** `backtest/fifa.py` (Dato FIFA archive, z-scored
  per date → regime-robust) + `backtest/compare_fifa.py` (2-var LS supremacy fit).
  **Finding: FIFA adds NO predictive value beyond Elo** — marginal coefficient is
  negative; elo_only beats elo+fifa on every bucket (competitive 0.1656 vs 0.1666,
  WC2022 0.2286 vs 0.2347). Per the data, cut RANK_W 0.7/0.3 → **0.85/0.15** (Elo
  dominant, FIFA a light anchor). Overall 40/40/20 stays (book/expert weights not
  RPS-tunable — no historical odds). Not yet redeployed (batch with M7).
- 2026-05-31: **M7 measured → cut.** Tested whether Maher's attack/defence *style*
  adds value beyond overall strength (`compare_ad.py` maher_dc vs style-stripped
  maher_overall): **near-identical** (competitive 0.1667 vs 0.1671; WC2022 0.2120
  vs 0.2129). So the att/def split adds ~no RPS; Maher's edge is its overall
  ratings — already captured (better) by the market+expert+Elo blend, which is
  more current and isn't backtestable. Per the guiding rule, the goal-model
  rewrite isn't justified → **M7 cut** (doc permits). The live v2 model stands.
  v2 core (M2–M5) + M6 are the shippable result.
- 2026-05-31: **M8 (worthwhile parts).** Added **knockout host edge** (Params
  ko_host_adv=30, reduced from the group edge 60): host nations USA/Mexico/Canada
  keep a home-soil edge in the knockouts (cancels if both hosts). Hosts' deep-run
  odds rise modestly (Mexico champ 1.2→2.3%, USA 0.7→1.2%). **Skipped** the rest
  per the doc's caution: xG (international xG too sparse), squad value (fragile
  scrape; M6 shows broad signals add ~nothing beyond Elo), latent tournament-form
  (invasive to thread + magnitude not backtest-validatable). **v2 complete.**

## In-tournament roadmap (captured 2026-06-01)

Once matches start (11 June 2026), the model should react to results, and we
should harvest the traffic. Planned, not yet built:

1. **SEO "today's game" predictions.** Per-match pages already exist
   (`/match/<a>-vs-<b>/`); add a daily-refreshed "today's games" angle/landing
   and surface the day's fixtures with their predictions for high-intent
   match-day searches.
2. **Home view top: today's & tomorrow's games.** Lead the homepage during the
   tournament with the upcoming fixtures + their W/D/L predictions (above the
   title race), so the live site is useful day-to-day.
3. **Snapshot pre-tournament odds + expert picks (stored locally).** Freeze the
   initial bookmaker odds and expert predictions before kickoff. The blend is
   inertial (Elo is slow-moving; initial odds/experts are fixed), so when the
   pre-tournament inputs are *wrong*, the blend underestimates the correction as
   results arrive. Keeping the baseline lets us measure the drift and
   deliberately **amplify** the delta (results vs. baseline) rather than let
   inertia damp it.
4. **Live hit-rate scoreboard.** Track the blend's hit rate as results come in,
   and compare it against each component alone — Elo-only, odds-only,
   experts-only. A live, public calibration scoreboard (and an internal signal
   for re-weighting if one component is clearly beating the blend).
