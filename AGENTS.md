# Contributing

Everything in this repository is public.

## Manifests

Edit only `.claude-plugin/marketplace.json` and `plugins/<name>/.claude-plugin/plugin.json`, then run `python3 scripts/sync_manifests.py`. It generates the Codex, Copilot CLI, Cursor and Agent Plugins manifests; CI fails when they are out of date.

- A plugin that is only text, such as skills, lives under `plugins/`. A plugin with source code stays in its own repository and is referenced, like `tigergraph` from [tigergraph-mcp](https://github.com/tigergraph/tigergraph-mcp).
- A plugin's `name` never changes once published. Set `displayName` and `description` on its marketplace entry, and leave `version` to the plugin's own `plugin.json`.

## Writing a skill

- Name it `tigergraph-<topic>`, the same as its folder. Keep `SKILL.md` short: when to use it, the core facts, and an index of `references/`. Agents often read only `SKILL.md`, so put rules that matter there.
- In the frontmatter, `description` says when to load the skill and hands off to overlapping skills ("Does NOT cover X — use tigergraph-y"). `compatibility` gives the oldest TigerGraph release it is written for. Bump `metadata.version` and the plugin `version` when the content changes.
- Write for the oldest supported release and tag newer behaviour inline, for example `[4.1+]` or `[before 4.1]`. Tell the agent to check the version before it relies on a tagged feature.
- Write for an agent in a non-interactive shell. Explain why rather than writing ALWAYS or NEVER; for risky actions, give the risk and a safe default and leave the decision to the user.
- End with an "Official documentation" section that links the pages backing the skill.

## Public content only

Skills ship to customers and public registries. Do not include internal repository names, source paths or class names, internal URLs, customer names, commands that print secrets or full configuration dumps (naming one in a warning is fine), or repair procedures for internal services (point to TigerGraph Support). When in doubt, keep to what [docs.tigergraph.com](https://docs.tigergraph.com) says.

## Evals

Every skill change comes with an eval case in `evals/cases/<skill>.json` that fails without the change and passes with it; CI checks for one. See [evals/README.md](evals/README.md).
