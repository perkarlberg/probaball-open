#!/usr/bin/env bash
# In-tournament daily refresh: pull new results, recompute Elo, refresh odds,
# then rebuild + reseed + redeploy so the live forecast reacts to games played.
#
#   ./daily_update.sh
#
# Why a full redeploy (not just reseed): elo_ratings.json and odds_snapshot.json
# are COPYed into the Cloud Run image, so new ratings/odds only reach the runtime
# via a backend image rebuild. Sequence: fetch results -> build Elo -> fetch odds
# -> deploy all (backend + reseed canonical + frontend).
#
# Cost: fetch_odds makes ONE the-odds-api call (1 credit, eu region). Daily for
# the ~5-week tournament is ~40 credits, well within the 500/mo plan.
set -euo pipefail

# Run manually, on demand: ./daily_update.sh
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"

# the-odds-api key (kept outside the repo).
if [ -f "$HOME/.claude/secrets/probaball-odds.env" ]; then
  set -a; . "$HOME/.claude/secrets/probaball-odds.env"; set +a
fi

echo "==> [$(date -u +%FT%TZ)] Refreshing international results (martj42)"
python3 -m backtest.fetch_data

echo "==> Rebuilding Elo from results"
python3 -m fitting.build_elo

if [ -n "${ODDS_API_KEY:-}" ]; then
  echo "==> Refreshing bookmaker odds (the-odds-api, 1 credit)"
  python3 -m fitting.fetch_odds || echo "   (odds refresh failed; keeping previous snapshot)"
else
  echo "==> ODDS_API_KEY not set — skipping odds refresh, keeping previous snapshot"
fi

echo "==> Deploying (backend image + reseed canonical + frontend)"
cd "$ROOT"
./deploy.sh all

# Log the day's tournament-stage forecast (+ book title prob) for the live
# model-vs-market scorecard. Reads the freshly-deployed canonical. Non-fatal.
echo "==> Logging tournament-forecast scorecard row"
python3 "$ROOT/backend/log_scorecard.py" || echo "   (scorecard log skipped; non-fatal)"

echo "==> [$(date -u +%FT%TZ)] Daily update complete."
