# TigerGraph plugins for Claude

The `tigergraph` plugin marketplace for [Claude Code](https://code.claude.com). It lists
TigerGraph's Claude plugins; each plugin lives in its own repository.

## Install

Add the marketplace once:

```bash
claude plugin marketplace add tigergraph/tigergraph
```

Then install the plugins you want:

```bash
claude plugin install tigergraph@tigergraph
```

To get new releases, run `claude plugin update <plugin>@tigergraph`.

## Plugins

| Plugin | What it does | Source |
|---|---|---|
| `tigergraph` | Connects Claude to any TigerGraph deployment — self-managed, on-premise, or TigerGraph Savanna — to explore the schema, run GSQL and Cypher, load data, and search vector embeddings. | [tigergraph/tigergraph-mcp](https://github.com/tigergraph/tigergraph-mcp/tree/main/plugins/tigergraph) |

See each plugin's README for requirements, configuration, and what it sends where.

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

A plugin lives in its own repository with a `.claude-plugin/plugin.json`. To list it here,
add an entry to [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json):

- `name` must match the `name` in the plugin's `plugin.json`, and never changes once
  published.
- `source` points at the plugin's repository: `{"source": "github", "repo": "tigergraph/<repo>"}`
  when the plugin is at the repository root, or a `git-subdir` source with a `path` when it
  is in a subfolder.
- Set `displayName` and `description` on the entry. Claude Code shows them before install,
  when it has not yet fetched the plugin's own `plugin.json`.
- Leave `version` out. Each plugin's `plugin.json` holds its version.

Check the result with `claude plugin validate ./ --strict` before opening a pull request.

## License

[Apache License 2.0](LICENSE)
