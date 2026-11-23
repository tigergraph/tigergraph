#!/bin/bash
# Install the marketplace in Codex and GitHub Copilot CLI from this checkout, in throwaway homes, and check that
# every plugin installs and every skill is found. Needs `codex` and `copilot` on PATH and network access to GitHub
# (the MCP plugin comes from another repo). Usage: scripts/smoke_install.sh
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; mkdir -p "$T/codex" "$T/copilot"
want=$(cd "$REPO" && ls -d plugins/*/skills/*/ | wc -l)
plugins=$(python3 -c 'import json,sys; print(" ".join(p["name"] for p in json.load(open(sys.argv[1]))["plugins"]))' "$REPO/.claude-plugin/marketplace.json")
fail=0

echo "== Codex $(codex --version)"
export CODEX_HOME="$T/codex"
codex plugin marketplace add "$REPO" >/dev/null 2>&1
for p in $plugins; do codex plugin add "$p@tigergraph" 2>&1 | grep -v WARNING || true; done
for p in $plugins; do [ -d "$CODEX_HOME/plugins/cache/tigergraph/$p" ] || { echo "Codex did not install $p"; fail=1; }; done
got=$(find "$CODEX_HOME/plugins/cache/tigergraph" -path '*/skills/*/SKILL.md' | wc -l)
[ "$got" -ge "$want" ] || { echo "Codex found $got skills, expected $want"; fail=1; }
unset CODEX_HOME

echo "== Copilot $(copilot --version | head -1)"
HOME="$T/copilot" copilot plugin marketplace add "$REPO" >/dev/null
# Check each plugin right after its install: with a local-directory marketplace, Copilot drops plugins it copied
# when it enables a live one. Users add the marketplace from GitHub, where this does not happen.
for p in $plugins; do
  HOME="$T/copilot" copilot plugin install "$p@tigergraph" | tail -1
  grep -q "\"name\": \"$p\"" "$T/copilot/.copilot/config.json" 2>/dev/null \
    || HOME="$T/copilot" copilot plugin list | grep -q "$p@tigergraph" \
    || { echo "Copilot did not install $p"; fail=1; }
done

[ $fail = 0 ] && echo "All plugins installed in Codex and Copilot."
exit $fail
