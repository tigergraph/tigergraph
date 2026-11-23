# TigerGraph plugins for AI coding agents

The `tigergraph` plugin marketplace for [Claude Code](https://code.claude.com), Codex, GitHub
Copilot CLI, Cursor and other agents that load plugins or skills.

| Plugin | What it gives the agent | Source |
|---|---|---|
| `tigergraph` | Connects to any TigerGraph deployment — self-managed, on-premise, or TigerGraph Savanna — to explore the schema, run GSQL and Cypher, load data, and search vector embeddings. | [tigergraph/tigergraph-mcp](https://github.com/tigergraph/tigergraph-mcp/tree/main/plugins/tigergraph) |
| `tigergraph-skills` | Skills for how a TigerGraph cluster works and how to operate it from the command line with `gadmin`, `gsql` and the cluster scripts. They need no database connection. | [plugins/tigergraph-skills](plugins/tigergraph-skills) |

See each plugin's README for requirements, configuration, and what it sends where.

## Install

### Claude Code

Add the marketplace once, then install the plugins you want:

```bash
claude plugin marketplace add tigergraph/tigergraph
claude plugin install tigergraph@tigergraph
claude plugin install tigergraph-skills@tigergraph
```

To get new releases, run `claude plugin update <plugin>@tigergraph`.

### Codex

```bash
codex plugin marketplace add tigergraph/tigergraph
codex plugin add tigergraph@tigergraph
codex plugin add tigergraph-skills@tigergraph
```

### GitHub Copilot CLI

```bash
copilot plugin marketplace add tigergraph/tigergraph
copilot plugin install tigergraph@tigergraph
copilot plugin install tigergraph-skills@tigergraph
```

### Cursor and other agents

Each local plugin also has a root `plugin.json` in the open [Agent Plugins](https://agent-plugins.org)
format, which Cursor, VS Code and Kiro load, and the repository has a Cursor marketplace manifest
that lists `tigergraph-skills`. To install only the skills in any agent that reads `SKILL.md` files,
use the [skills CLI](https://skills.sh):

```bash
npx skills add tigergraph/tigergraph
```

## Skills

| Skill | Use it for |
|---|---|
| `tigergraph-cli` | `gadmin`, `gsql` and the cluster scripts on a TigerGraph node |
| `tigergraph-cluster` | Services, partitions and replicas, and how queries and loading flow through a cluster |

Skills track the TigerGraph releases that are currently supported. Each skill states its
baseline in the `compatibility` field, and features that need a newer release are tagged
inline, for example `[4.1+]`.

## Already added the marketplace from tigergraph-mcp?

If you ran `claude plugin marketplace add tigergraph/tigergraph-mcp` before, your
installed plugins keep working and keep receiving updates; there is nothing to do.

A marketplace name can be registered only once, so to switch to this repository you remove
the old one first. Removing a marketplace uninstalls its plugins along with their saved
options, so you will enter your TigerGraph host and credentials again:

```bash
claude plugin marketplace remove tigergraph
claude plugin marketplace add tigergraph/tigergraph
claude plugin install tigergraph@tigergraph
```

## Adding a plugin

A plugin with source code lives in its own repository and is referenced from here, like
`tigergraph`. A plugin that is only text, such as skills, lives under [`plugins/`](plugins).
See [AGENTS.md](AGENTS.md) for the manifest rules, the skill authoring rules, and the checks
CI runs, and [evals/README.md](evals/README.md) for the test cases every skill change comes with.

## License

[Apache License 2.0](LICENSE)
