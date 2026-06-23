#!/usr/bin/env bash
# Publish a clean snapshot of the tracked source to the PUBLIC GitHub mirror.
#
# This (private) dev repo `probaball` stays private. publish.sh exports exactly
# the git-tracked files at HEAD — minus the internal playbook — into a clone of
# the public repo `probaball-open`, commits the diff, and pushes. Run it after
# committing here (and it's wired into deploy.sh so the mirror never goes stale).
#
#   ./publish.sh            # snapshot HEAD → probaball-open
#   PUBLIC_REPO=… ./publish.sh
#
# Why a snapshot mirror and not just "make this repo public": the dev history
# carries internal ops notes (and once carried a leaked free-tier API key), so
# we publish a clean tree from a clean history instead of rewriting this one.
set -euo pipefail

PUBLIC_REPO="${PUBLIC_REPO:-git@github.com:perkarlberg/probaball-open.git}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$HERE/.publish/probaball-open"

# Tracked paths to NOT publish (relative to repo root). Everything else that
# git tracks at HEAD is published. CLAUDE.md + .claude/ are the internal
# operations playbook (gcloud secret names, deploy-token flow, secret paths).
EXCLUDE=(CLAUDE.md .claude)

SHA="$(git -C "$HERE" rev-parse --short HEAD)"
DATE="$(date +%Y-%m-%d)"

# Persistent clone of the public repo (gitignored). Clone on first run.
if [ ! -d "$WORK/.git" ]; then
  rm -rf "$WORK"; mkdir -p "$(dirname "$WORK")"
  if ! git clone --quiet "$PUBLIC_REPO" "$WORK" 2>/dev/null; then
    echo "==> public repo not clonable yet — initialising a fresh one at $WORK"
    mkdir -p "$WORK"; git -C "$WORK" init --quiet
    git -C "$WORK" remote add origin "$PUBLIC_REPO"
    git -C "$WORK" branch -M main
  fi
else
  git -C "$WORK" fetch origin --quiet 2>/dev/null || true
  git -C "$WORK" reset --hard origin/main --quiet 2>/dev/null || true
fi

# Replace the working tree (keep .git) with HEAD's tracked files, minus excludes.
find "$WORK" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
git -C "$HERE" archive HEAD | tar -x -C "$WORK"
for p in "${EXCLUDE[@]}"; do rm -rf "$WORK/${p:?}"; done

cd "$WORK"
git add -A
if git diff --cached --quiet; then
  echo "Nothing to publish — public mirror already matches probaball@$SHA."
  exit 0
fi
git commit --quiet -m "Sync from probaball@$SHA ($DATE)"
git push -u origin main
echo "==> Published probaball@$SHA to $PUBLIC_REPO"
