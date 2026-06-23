# World Cup 2026 — Monte Carlo Simulation Engine

**Handoff documentation** · companion to `vm2026_sim.py`

This document describes the data sources, modelling assumptions, parameters,
and known limitations of the tournament simulator so another team can continue
development without reverse-engineering the code.

---

## 1. What the engine does

It simulates the entire 48-team tournament — group stage → Round of 32 →
final — as a stochastic process, and repeats the whole tournament `N` times
(Monte Carlo). Aggregating across runs yields, for every team, the probability
of reaching each stage and of winning the title.

```
python3 vm2026_sim.py 20000     # 20,000 full-tournament simulations
```

Run-to-run results are reproducible because the RNG is seeded
(`random.seed(42)` in `main()`). Remove or vary the seed for independent runs.

---

## 2. Data sources

All inputs were collected on **30 May 2026**. Two categories: structural
(the bracket, fixed) and strength estimates (the ratings, the model's only
free data input).

### 2.1 Group composition (structural — authoritative)

The 12 groups follow the official Final Draw held **5 December 2025** at the
Kennedy Center, Washington D.C., completed by the playoff results of
**26 & 31 March 2026**. Cross-checked across multiple outlets:

| Source | Used for |
|---|---|
| Britannica — 2026 FIFA World Cup Teams | Full group listing A–L |
| NBC Sports — "2026 World Cup groups confirmed" | Verification of groups |
| Yahoo Sports — 2026 World Cup schedule | Verification + confederation list |
| Bola 2026 / soccer2026.app | Verification of all 12 groups |

The groups are hard-coded in the `GROUPS` dict and should be treated as ground
truth — they will not change before kickoff (11 June 2026).

### 2.2 Team strength — FIFA World Ranking (1 April 2026)

Team strength `R` is the **FIFA/Coca-Cola World Ranking points**, release of
**1 April 2026** (the last update before the tournament; next update 9 June
2026).

| Source | Used for |
|---|---|
| Wikipedia — FIFA Men's World Ranking | Exact points, top 20 |
| ESPN — FIFA Men's Top 50, April 2026 | Rank positions 1–50 + qualified honorable mentions |

**Important data-quality caveat.** Only the **top 20** teams have exact
published points wired in. For teams ranked below 20, points are **estimated**
by interpolating from their known rank position against the top-20 points
curve. These estimates are flagged in code and are the single biggest source
of model error for mid- and lower-tier teams. See §6.

### 2.3 Market calibration — bookmaker title odds

Not a direct model input. Used only to **sanity-check** that simulated title
probabilities resemble the betting market. Collected from DraftKings, BetMGM,
CBS/SportsLine, FOX Sports, Covers, RotoWire (all late May 2026). Market top:
Spain ≈ +475, France ≈ +500, England ≈ +650, Brazil ≈ +800, Argentina ≈ +900.

The simulator reproduces this ordering at the top, with one known divergence:
the market discounts Argentina more heavily than pure ranking does (title
defence difficulty, squad age) — judgement factors outside a ratings model.

---

## 3. Match model

A single match is a **bivariate Poisson goal model** driven by the rating gap.

For teams A and B with ratings `R_A`, `R_B`:

```
diff   = (R_A + home_A) − (R_B + home_B)
mu     = diff × GOAL_SCALE                 # goal-supremacy term
λ_A    = max(0.15, BASE_GOALS/2 + mu/2)    # expected goals, team A
λ_B    = max(0.15, BASE_GOALS/2 − mu/2)    # expected goals, team B
```

Goals for each side are drawn independently as `Poisson(λ)`. The `0.15` floor
prevents a degenerate zero-goal expectation for heavy underdogs.

* **Home advantage** (`home_X`) adds `HOME_ADV` rating points to host nations
  (USA, Mexico, Canada) **in the group stage only**. Knockout matches are
  treated as neutral venues.
* **Knockout draws** are resolved by a penalty shootout with a mild bias toward
  the stronger side: `P(A wins) = 0.5 + (R_A − R_B) × 0.0004`, clamped to
  [0.15, 0.85]. The clamp reflects that shootouts are close to a coin flip.

### Parameters (in `vm2026_sim.py`, top of file)

| Constant | Value | Meaning | Effect of increasing |
|---|---|---|---|
| `GOAL_SCALE` | 0.0048 | Goals per rating-point gap | Favourites win by more / more often |
| `BASE_GOALS` | 2.65 | Avg. total goals in an even match | Higher-scoring games, more variance |
| `HOME_ADV` | 60 | Rating bonus for host nations (group only) | Hosts advance more often |

These were tuned so the simulated title distribution matches the bookmaker
market at the top. They are not estimated from match data — re-tuning against
historical results is a natural next step (§7).

---

## 4. Tournament structure

1. **Group stage** — each group plays all 6 round-robin matches. Teams are
   ranked by: points → goal difference → goals for → FIFA rating → random
   tiebreak. (The rating tiebreak is a pragmatic stand-in for FIFA's fair-play
   and drawing-of-lots rules.)
2. **Qualification** — top 2 of each group (24 teams) plus the **8 best
   third-placed teams**, ranked by the same key, advance. Total: 32.
3. **Knockout** — single elimination R32 → R16 → QF → SF → Final.

### Bracket seeding — known simplification

The 32 qualifiers are seeded into a **balanced single-elimination bracket**
(`_seeding_order` / `seed_bracket`): strongest teams maximally separated so
seeds 1 and 2 can only meet in the final. This is **not** FIFA's actual fixed
mapping, which uses a predetermined table assigning each group winner a
specific path and slotting the eight third-place teams by a fixed lookup keyed
on *which* groups they came from. Our approximation keeps the bracket monotonic
(better teams get easier expected paths) but does not reproduce the exact
real-world matchups. Impact on title odds is marginal; impact on a *specific*
team's projected opponent can be material. Replacing this with the official
table is the highest-value structural improvement (§7).

---

## 5. Output

`main()` prints, for the top 24 teams by title probability: group, and the
percentage of simulations reaching champion / final / semi / quarter / R16.
The functions also expose per-stage counts via the `progress` dict and group
finishing positions, which downstream scripts can query directly (see the
Group F position-distribution analysis for an example pattern).

---

## 6. Known limitations

1. **Estimated ratings below rank 20.** The largest error source. Mid-table
   and lower teams' strengths are interpolated, not exact. Wire in the full
   published FIFA points table (all 48 teams) to fix.
2. **Ratings are static.** No in-tournament form, injuries, suspensions, or
   squad-news adjustments. Messi/Haaland/Yamal fitness, etc., are invisible.
3. **Independent-Poisson goals.** No explicit correlation between the two
   sides' scores, no draw-inflation term; real football has slightly more draws
   than independent Poisson predicts.
4. **Approximate knockout bracket.** See §4 — not the official FIFA mapping.
5. **Parameters tuned to market, not to match data.** `GOAL_SCALE`,
   `BASE_GOALS`, `HOME_ADV` are calibrated to bookmaker odds, which already
   embed market bias.
6. **Knockout venues treated as neutral.** Several knockout games are in fact
   on or near host soil; no host edge is applied past the group stage.
7. **Tiebreakers simplified.** Fair-play points and drawing of lots replaced by
   rating + random.

---

## 7. Suggested next steps (priority order)

1. **Complete the ratings table** — replace all estimated sub-rank-20 points
   with the official 9 June 2026 FIFA release (the final pre-tournament update).
2. **Implement FIFA's official knockout mapping** for group winners, runners-up
   and the eight third-place permutations. This is a fixed lookup table.
3. **Calibrate the goal model against historical international results**
   (e.g. last two World Cup cycles) instead of bookmaker odds; consider a
   Dixon-Coles low-score correction for the draw bias.
4. **Blend ratings with market odds** — convert title odds to implied
   probabilities and use them as a prior on team strength, so expert/market
   judgement (Argentina discount, etc.) enters the model.
5. **Add per-match overrides** for injuries/suspensions (a simple rating delta
   per team per match).
6. **Confidence intervals** — report Monte Carlo standard error per probability
   (≈ sqrt(p(1−p)/N)) so users know the resolution at a given N.
7. **Vectorise** with NumPy if N grows large (current pure-Python loop is fine
   to ~10^5 but slow beyond).

---

## 8. File map

| File | Contents |
|---|---|
| `vm2026_sim.py` | Engine: data, match model, group + knockout logic, CLI |
| `METHODOLOGY.md` | This document |

Engine entry points worth knowing: `simulate_group`, `best_thirds`,
`seed_bracket`, `play_bracket`, `simulate_tournament`, `main`. Tweak the three
constants at the top of the file to change model behaviour; edit `GROUPS` to
change teams or ratings.

---

*Data collected 30 May 2026. Ratings: FIFA World Ranking, 1 April 2026 release.
Groups: official Final Draw 5 Dec 2025 + playoffs 26/31 Mar 2026. This project
is not affiliated with or endorsed by FIFA.*
