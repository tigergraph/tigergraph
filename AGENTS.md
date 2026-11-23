# Authoring guide

Rules for adding plugins to the marketplace and for adding or changing skills. Everything here is public.

## Layout

```
.claude-plugin/marketplace.json        marketplace "tigergraph" (source of truth)
plugins/tigergraph-skills/
  .claude-plugin/plugin.json           plugin manifest (source of truth)
  .claude-plugin/icon.png              listing icon
  plugin.json                          generated: Agent Plugins manifest for Codex, Cursor, Copilot and others
  skills/<skill-name>/
    SKILL.md
    references/*.md                    loaded on demand from SKILL.md
.agents/plugins/marketplace.json       generated: Codex marketplace
.github/plugin/marketplace.json        generated: Copilot CLI marketplace
.cursor-plugin/marketplace.json        generated: Cursor marketplace
evals/                                 test cases and the runner; see evals/README.md
scripts/                               manifest generator and checks
```

Edit only the Claude Code manifests, then run `python3 scripts/sync_manifests.py` to regenerate the others. CI fails when they differ.

## Marketplace entries

- A plugin that is only text, such as skills, lives under `plugins/` with a local `source` (`"./plugins/<name>"`).
- A plugin with source code lives in its own repository and is referenced: `{"source": "github", "repo": "tigergraph/<repo>"}` when the plugin is at the repository root, or a `git-subdir` source with a `path` when it is in a subfolder. The `tigergraph` plugin (MCP) is referenced this way from [tigergraph-mcp](https://github.com/tigergraph/tigergraph-mcp). Cursor's marketplace lists only local plugins, so referenced ones are left out of it.
- `name` must match the `name` in the plugin's `plugin.json`, and never changes once published.
- Set `displayName` and `description` on the entry. Claude Code shows them before install, when it has not yet fetched the plugin's own `plugin.json`. For a referenced plugin, keep them in step with its `plugin.json`.
- Leave `version` out. Each plugin's `plugin.json` holds its version.

## Naming

- Skill names start with `tigergraph-`, in lowercase kebab-case, and match the folder name.
- Keep `SKILL.md` short: when to use the skill, the core facts, and an index of `references/`.
- Write for an agent, not a person at a terminal: assume a non-interactive shell, say what to do when a command prompts for input, and cover the case where the agent can only hand commands to the user.
- Explain why instead of writing ALWAYS or NEVER. For risky actions, give the risk and a safe default, and leave the decision to the user.
- State each fact in one place. Other files point to it instead of repeating it, so an agent that reads only one file never sees two versions.
- End each `SKILL.md` with an "Official documentation" section: the versioned URL pattern and the pages that back the skill.

## Frontmatter

```yaml
---
name: tigergraph-example
description: What the skill does and when to load it. Does NOT cover X — use tigergraph-y.
compatibility: TigerGraph 3.10 or later, self-managed.
license: Apache-2.0
metadata:
  author: TigerGraph
  version: "0.1.0"
---
```

- `description` names the trigger situations and, with "Does NOT cover … — use …", hands off to sibling skills that overlap.
- `compatibility` states the oldest TigerGraph release the skill is written for and the deployment types it applies to.
- `metadata.version` is the skill's own version. Bump it, and the plugin `version` in `plugin.json`, when the content changes.

## Version compatibility

- Write for the oldest supported release in `compatibility`. Tag anything newer inline as `[4.1+]`, and behaviour that was later removed as `[before 4.1]` (or `[3.10 only]` when it applies to a single release line).
- Tell the agent to detect the version before relying on a tagged feature (`gadmin version` on a node, or ask the user). When the version is unknown, use only untagged features.
- One `main` branch. Do not keep per-release branches or copies of a skill.

## Public content only

These skills ship to customers and to public registries. Before you open a PR, check that the change contains none of:

- source repository names, source paths, or internal class, constant or file names;
- internal URLs (issue tracker, wiki, internal docs or repositories) or customer names;
- instructions to run commands that print secrets or full configuration dumps. Naming such a command inside an explicit warning not to run it is fine, since an agent can only avoid a command it recognizes;
- repair or reset procedures for internal services. Point to TigerGraph Support instead.

When in doubt, keep to what [docs.tigergraph.com](https://docs.tigergraph.com) already says.

## Evals

Every change to a skill comes with an eval case that fails without the change and passes with it: a new case in `evals/cases/<skill>.json`, or an updated one. CI checks for it. See [evals/README.md](evals/README.md).

## Plugin rules

- No symlinks inside `plugins/`.
- Run `claude plugin validate ./ --strict` and `claude plugin validate ./plugins/tigergraph-skills --strict` before you push. CI runs the same checks, plus the Agent Skills format check (`scripts/check_skills.py`) and an install test in Codex and Copilot CLI (`scripts/smoke_install.sh`).
