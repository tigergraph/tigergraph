#!/usr/bin/env python3
"""Generate the other agents' manifests from the Claude Code ones, so every agent sees the same plugins.

Sources of truth (edit these):
  .claude-plugin/marketplace.json            the marketplace
  plugins/<name>/.claude-plugin/plugin.json  each local plugin

Generated (do not edit by hand):
  plugins/<name>/plugin.json         Agent Plugins 1.0 manifest: Codex, Cursor, Copilot, VS Code, Kiro
  .agents/plugins/marketplace.json   Codex marketplace
  .github/plugin/marketplace.json    Copilot CLI marketplace (Copilot does not read git-subdir sources)
  .cursor-plugin/marketplace.json    Cursor marketplace (local plugins only; Cursor cannot fetch other repos)

Usage: sync_manifests.py [--check]   --check exits 1 if a generated file is missing or stale.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PORTABLE_FIELDS = ("name", "version", "description", "author", "homepage", "repository", "license", "keywords")


def load(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return json.load(f)


def local_path(entry):
    src = entry["source"]
    return src if isinstance(src, str) else None


def agent_plugin(manifest):
    out: dict = {"$schema": AGENT_PLUGINS_SCHEMA}
    out.update({k: manifest[k] for k in PORTABLE_FIELDS if k in manifest})
    if "author" in out:  # the standard allows only name, email, url
        out["author"] = {k: v for k, v in out["author"].items() if k in ("name", "email", "url")}
    return out


def codex_source(entry):
    src = entry["source"]
    if isinstance(src, str):
        return {"source": "local", "path": src}
    return src


def copilot_source(entry):
    src = entry["source"]
    if isinstance(src, dict) and src.get("source") == "git-subdir":
        repo = src["url"].removeprefix("https://github.com/").removesuffix(".git")
        out = {"source": "github", "repo": repo, "path": src["path"]}
        if "ref" in src:
            out["ref"] = src["ref"]
        return out
    return src


def generate():
    mkt = load(".claude-plugin/marketplace.json")
    files = {}
    for entry in mkt["plugins"]:
        path = local_path(entry)
        if path:
            manifest = load(os.path.join(path, ".claude-plugin/plugin.json"))
            files[os.path.join(path.removeprefix("./"), "plugin.json")] = agent_plugin(manifest)

    files[".agents/plugins/marketplace.json"] = {
        "name": mkt["name"],
        "interface": {"displayName": "TigerGraph"},
        "plugins": [
            {
                "name": e["name"],
                "source": codex_source(e),
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Developer Tools",  # Codex catalog taxonomy; database plugins such as supabase use it
            }
            for e in mkt["plugins"]
        ],
    }

    copilot = {k: v for k, v in mkt.items() if k not in ("$schema", "plugins")}
    copilot["plugins"] = [{**e, "source": copilot_source(e)} for e in mkt["plugins"]]
    files[".github/plugin/marketplace.json"] = copilot

    files[".cursor-plugin/marketplace.json"] = {
        "name": mkt["name"],
        "owner": {k: v for k, v in mkt["owner"].items() if k in ("name", "email")},
        "metadata": {"description": mkt["description"]},
        "plugins": [
            {"name": e["name"], "source": e["source"].removeprefix("./"), "description": e["description"]}
            for e in mkt["plugins"] if local_path(e)
        ],
    }
    return files


def main():
    check = "--check" in sys.argv[1:]
    stale = []
    for rel, data in generate().items():
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        full = os.path.join(ROOT, rel)
        current = open(full).read() if os.path.exists(full) else None
        if current == text:
            continue
        if check:
            stale.append(rel)
        else:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write(text)
            print(f"wrote {rel}")
    if stale:
        print("Out of date: " + ", ".join(stale), file=sys.stderr)
        print("Run `python3 scripts/sync_manifests.py` and commit the result.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
