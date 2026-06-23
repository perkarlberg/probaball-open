# World Cup Simulator — v2 Design & Handover

**Target architecture for the next iteration** · companion to `vm2026_sim.py`
and `METHODOLOGY.md`

This document specifies the planned upgrade from the current v1 engine (single
FIFA-points scalar + hand-tuned Poisson) to a v2 engine with a **blended
strength estimate**, a **data-fitted goal model**, and **improved tournament
logic**. Each item carries a feasibility call so scope can be cut cleanly if
data or time runs short.

> **Guiding rule:** nothing in this doc ships without first standing up the
> backtest harness (§1). Every change is judged by whether it lowers
> out-of-sample Ranked Probability Score — not by whether it looks more
> sophisticated.

---

## 1. Prerequisite — scoring harness (build this first)

Before changing any input or model, add a way to measure predictive power.
Without it, "improvement" is unfalsifiable.

- **Ranked Probability Score (RPS)** on match W/D/L — the standard metric for
  ordered outcomes; penalises confident wrong predictions and rewards
  calibration. Primary metric.
- **Brier score / log-loss** on the title market and on advance-from-group.
- **Backtest set:** the last 2–3 World Cups (2018, 2022, and qualifying-era
  internationals) — predict each match *using only information available
  before it*, then score.

**Feasibility: HIGH.** Pure bookkeeping; no new data beyond historical results.
Do this first.

---

## 2. Blended strength estimate (core concept change)

v1 used a single number (FIFA points) as team strength. v2 replaces it with a
**weighted blend of three independent signals**, each converted to a common
scale (implied win-probability or an Elo-equivalent) before blending.

### 2.1 The weighting

Equal thirds were considered but rejected — the three signals are not equally
predictive. Markets are very hard to beat and rankings are noisier, so:

| Component | Weight | Rationale |
|---|---:|---|
| Rankings blend (§2.2) | **40%** | Broad, objective, always available |
| Bookmaker probabilities (§2.3) | **40%** | Strongest single predictor; embeds form/injuries/judgement |
| Expert forecasts (§2.4) | **20%** | Adds human judgement markets may miss; thinner, noisier data |

Treat these weights as **defaults to be tuned**, not fixed constants — once §1
exists, grid-search the weights against backtest RPS and let the data confirm
or adjust the 40/40/20 split.

### 2.2 Rankings sub-blend (the 40% bucket)

Itself a blend of up to three ranking systems, **Elo weighted most**:

| Sub-signal | Suggested weight | Source | Feasibility |
|---|---:|---|---|
| **Elo rating** | ~60% | eloratings.net / World Football Elo | HIGH — free, designed for prediction |
| **FIFA ranking** | ~25% | FIFA / Wikipedia | HIGH — already wired in v1 |
| **Squad market value** | ~15% | Transfermarkt aggregate | MEDIUM — public but scraping is fiddle; *include only if easily available* |

Elo gets the most weight because it is explicitly built to predict match
outcomes (per-match updates with margin and venue), whereas FIFA points are an
accumulation system. If squad value proves hard to source cleanly, drop it and
renormalise Elo/FIFA to ~70/30 — do **not** block the release on it.

**Feasibility: HIGH** for Elo+FIFA; **MEDIUM/optional** for squad value.

### 2.3 Bookmaker probabilities — de-vigging (the 40% bucket)

Raw odds include the bookmaker's margin ("vig"/"overround"); they must be
**de-vigged into true implied probabilities** before use.

1. Convert each outcome's odds to a raw implied probability (`1/decimal_odds`).
2. Sum across all outcomes in the market → the overround (>100%).
3. Normalise so probabilities sum to 1. (Start with simple proportional
   normalisation; consider Shin's method or the power method later — they
   handle favourite–longshot bias better.)

Collect from several books and average to reduce single-book noise. Use both
the **outright title market** (tournament-level prior) and **per-match
markets** where available (sharpest match-level signal).

**Feasibility: HIGH** for the math and the title market. **MEDIUM** for full
per-match coverage — odds for late knockout matchups don't exist until the
bracket forms, so use them for known fixtures and fall back to model-derived
probabilities deeper in the tree.

### 2.4 Expert forecasts (the 20% bucket)

Published pre-tournament predictions: statistical-model outputs
(FiveThirtyEight-style, Opta supercomputer, university models) and reputable
analyst tip sheets. Convert each to an implied per-team title/advance
probability and average.

**Feasibility: MEDIUM.** Aggregated qualitative tips are noisier and need
hand-curation; model-based forecasts (Opta etc.) are cleaner. If clean
expert data is thin, **fold this bucket's weight into bookmaker odds** (markets
already aggregate expert opinion) rather than inventing numbers — i.e. degrade
gracefully to a 50/50 rankings/market blend.

### 2.5 Combination mechanics

Convert all three buckets to the **same scale** before blending. Cleanest:
map each to a strength rating on an Elo-like scale (invert the logistic that
turns rating gaps into win probabilities), blend the ratings linearly with the
weights above, then feed the blended rating into the goal model (§3). Blending
on the rating scale is more stable than blending probabilities directly.

---

## 3. Goal-model upgrades

### 3.1 Attack/defence split + Bayesian hierarchical model

Replace the single scalar with **separate attack and defence parameters per
team**, estimated in a **Bayesian hierarchical model**. Team parameters are
drawn from a shared prior (partial pooling), which is exactly what stabilises
estimates for the lower-ranked sides where v1 currently interpolates.

- **Why:** gives attack/defence strengths *with uncertainty*, propagates that
  uncertainty into the simulation, and pools information across teams.
- **How:** a standard hierarchical Poisson goal model fit with MCMC (PyMC or
  Stan). The blended strength from §2 enters as an informative prior on each
  team's overall level, so even teams with few recent matches are anchored.
- **Feasibility: MEDIUM.** Well-trodden in the literature and very feasible
  technically, but it's the largest single build (model spec, sampler,
  convergence checks) and adds a runtime/tooling dependency. **Recommended but
  cuttable:** if time is short, ship an attack/defence split fit by simpler
  MLE first, and add the Bayesian layer in a later pass. The attack/defence
  split alone captures much of the benefit.

### 3.2 Dixon–Coles low-score correction

Add the Dixon–Coles dependence term to correct the independent-Poisson model's
under-prediction of 0–0, 1–0, 0–1, 1–1 — i.e. the draw bias noted in v1's
limitations.

- **Feasibility: HIGH.** A small, well-documented closed-form adjustment to the
  score-probability matrix plus one extra parameter (ρ) to estimate. Cheap,
  high-value, do it alongside the goal-model rebuild.

### 3.3 Time-weighted form via xG

Weight recent matches more than old ones (exponential decay), and use
**expected goals (xG)** rather than actual scorelines as the performance signal
— xG is less noisy and more predictive of future results.

- **Feasibility: HIGH** for time-decay weighting (a multiplier in the
  likelihood). **MEDIUM** for xG — international-match xG is less uniformly
  available than club data; source what exists (FBref/StatsBomb-derived) and
  fall back to actual goals where xG is missing.

---

## 4. Tournament-logic upgrades

### 4.1 Official FIFA knockout mapping

Replace the balanced-bracket approximation with FIFA's **fixed lookup table**
assigning each group winner/runner-up a specific path, plus the predetermined
mapping of the eight third-place teams keyed on which groups they came from.

- **Why:** barely moves *title* odds but materially changes any *specific*
  team's projected opponents and path difficulty.
- **Feasibility: HIGH.** It's a static table; the work is transcribing it
  correctly and validating against a published bracket. Highest-value
  structural fix.

### 4.2 Per-tournament latent form draw

Draw a small per-team "tournament form" offset once per simulated tournament,
applied to all that team's matches, so the seven matches aren't fully
independent (captures momentum/streak effects).

- **Feasibility: MEDIUM.** Easy to code; the honest difficulty is *calibrating*
  how big the effect should be without overfitting. Add after the core model
  is scoring well, and only keep it if it lowers backtest RPS.

### 4.3 Host edge in knockout rounds

Extend the host-nation advantage past the group stage for knockout games played
on or near home soil (currently neutral everywhere in the knockouts).

- **Feasibility: HIGH.** Reuse the existing `HOME_ADV` mechanism, gated on
  venue. Minor effort.

---

## 5. Recommended sequencing

Ordered by bang-for-buck, each step independently shippable:

1. **RPS backtest harness** (§1) — unlocks measuring everything else. *HIGH.*
2. **Elo + FIFA rankings blend** replacing the bare FIFA scalar (§2.2). *HIGH.*
3. **De-vigged bookmaker probabilities** blended in at 40% (§2.3). *HIGH.*
4. **Dixon–Coles correction** + **attack/defence split** (§3.2, §3.1 MLE
   version). *HIGH / MEDIUM.*
5. **Official FIFA knockout mapping** (§4.1). *HIGH.*
6. **Expert-forecast bucket** at 20%, weights tuned on backtest (§2.4). *MEDIUM.*
7. **Bayesian hierarchical layer** on the goal model (§3.1 full). *MEDIUM.*
8. **Time-weighted xG form** (§3.3), **squad market value** (§2.2), **latent
   form draw** (§4.2), **knockout host edge** (§4.3) — refinements, keep each
   only if it improves backtest RPS. *MEDIUM / optional.*

Steps 1–5 convert the engine from "plausible ordering" to "calibrated
forecasts" and are all high-feasibility. Steps 6–8 are incremental polish with
diminishing returns and more data/tuning risk.

---

## 6. Data sources to add (summary)

| Source | Feeds | Public? | Feasibility |
|---|---|---|---|
| eloratings.net / World Football Elo | Rankings (Elo) | Yes, free | HIGH |
| Bookmaker odds (multiple books, title + per-match) | Market probabilities | Yes | HIGH (title) / MED (per-match) |
| Opta/model-based public forecasts | Expert bucket | Partly | MEDIUM |
| Transfermarkt squad values | Rankings (value) | Yes, scrape | MEDIUM, optional |
| Historical results 2018/2022 + quals | Backtesting + model fit | Yes | HIGH |
| xG data (FBref/StatsBomb-derived) | Time-weighted form | Partly | MEDIUM |

---

## 7. What stays the same

- Monte Carlo structure (simulate full tournament, repeat `N` times, aggregate).
- Group → R32 → final progression and the 8-best-thirds qualification rule.
- Seeded RNG for reproducibility.
- The CLI shape (`python3 sim.py N`) and per-stage probability output.

The v2 work swaps **what feeds team strength** and **how a single match is
modelled**, and tightens **bracket realism** — the simulation scaffold around
those is sound and should be reused.

---

*Design doc only — no v2 code written yet. Weights (40/40/20 and the rankings
sub-blend) are starting points to be tuned against the §1 backtest, not fixed
constants. Not affiliated with or endorsed by FIFA.*
