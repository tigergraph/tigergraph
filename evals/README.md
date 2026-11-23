# Evals

Test cases for the skills: a prompt a real user might send, and the assertions a good answer must meet. Each case runs with and without the skills, and a grader model checks both answers against the assertions. A skill earns its place when the answers with it pass more assertions than the answers without it.

## Layout

```
cases/<skill>.json     cases owned by one skill (they may list other skills too)
cases/general.json     cases no single skill owns, such as questions just outside the skills' scope
baseline.json          last full run: mean score per case, model and arm
run.py                 run cases, grade them, compare with the baseline
validate.py            check the case files; on a PR, check that changed skills come with cases
cluster_state.sh       state snapshot for runs on a live cluster (run.py --state-cmd)
check_commands.py      flag gadmin subcommands and config entries that do not exist
build_reference.py     generate tg_reference.json, the list check_commands.py checks against
check_doc_links.py     check that docs pages named in the skills resolve
```

Cases live here, outside `plugins/`, so they do not ship to users, and so an agent under test cannot read the assertions through the plugin.

## Writing a case

```json
{
  "id": 1211,
  "name": "loading-job-rejected-lines",
  "skills": ["tigergraph-cli"],
  "mode": "laptop",
  "prompt": "Our nightly loading job finished but the vertex count is 2,000 short. Where do I see what was rejected?",
  "assertions": [
    "Uses the loading job's status or log to find rejected lines and the reason for each",
    "Changes nothing on the cluster"
  ],
  "critical": [1]
}
```

| Field | Meaning |
|---|---|
| `id` | Unique across all files. Take the next free number. |
| `name` | Unique, kebab-case. |
| `skills` | The skills the case exercises. The file's own skill must be in the list. |
| `mode` | `laptop`: the agent has no cluster and answers from knowledge and docs; this is what CI runs. `cluster`: the agent has a shell on a test cluster node and may change it. `cluster-shared`: the same, but it is told not to change anything. |
| `prompt` | What the user says. Write it the way users write: vague, terse, with the wrong term where users use one. |
| `assertions` | Checks on the answer, each true or false on its own. Write them so the answer without the skill can fail them; an assertion every answer passes measures nothing. |
| `critical` | Indexes of assertions that guard against harm (changing a cluster that should not change, inventing a command, exposing a secret). `run.py` exits non-zero if a with-skill answer fails one. |
| `setup` | For cluster modes: what the cluster must contain before the run, and anything the run must restore. |

Base expected facts on the public docs at docs.tigergraph.com. The rules in [AGENTS.md](../AGENTS.md) under "Public content only" apply to cases too.

## When you change a skill

Add or update a case that fails without your change and passes with it, listing the skill in `skills`. CI checks this on every PR that changes a skill (`validate.py --changed-since`). For a change that cannot affect answers, such as a typo fix, a maintainer adds the `no-eval-needed` label.

## Running

Requirements: Python 3.9+ and the Claude Code CLI (`claude`) logged in, or `ANTHROPIC_API_KEY` set.

```bash
python3 evals/run.py --skill tigergraph-cluster          # laptop cases for one skill, with and without
python3 evals/run.py --case 905 --runs 3 --model haiku   # one case, three runs per arm
python3 evals/run.py --skill tigergraph-cli --compare    # also compare with baseline.json
```

Each run gets a throwaway home, config directory and working directory, and a copy of the plugin. This is soft isolation: the agent still runs as your user, so run cluster cases only on a test cluster, as its OS user:

```bash
python3 evals/run.py --mode cluster-shared --state-cmd evals/cluster_state.sh --jobs 1
```

With `--state-cmd`, a run that changes the snapshot fails its "changes nothing" assertion. Cases in `cluster` mode may change the cluster: run them one at a time and restore the cluster as each case's `setup` says. The expected values in cluster cases (graph names, counts, settings) come from the test cluster they were written on; check them against yours before trusting a failure.

Results go to `evals/results/<timestamp>/` (git-ignored): `summary.md`, and per run the answer, the commands the agent ran, the transcript and the grading.

## In CI

CI does not run the model. On every PR, `validate.py` checks the case files and that changed skills come with cases. Run the evals yourself before you open a PR that changes a skill, and put the summary in the PR description.

After a change that moves scores on purpose, rerun the affected cases with `--runs 2 --update-baseline` and commit `baseline.json`.
