#!/usr/bin/env python3
"""Run eval cases in headless Claude Code with and without the skills, grade each answer, and compare.

Each run gets a throwaway HOME, config dir and working directory, a copy of the plugin (so the agent
cannot read evals/ or the rest of the repo through it), no user settings, plugins, MCP servers or memory.
That is soft isolation: the agent runs as your user. Run cluster cases only on a test cluster.

Examples:
  evals/run.py --skill tigergraph-cluster                       laptop cases for one skill, both arms
  evals/run.py --case 905 --case 1106 --runs 2 --model haiku
  evals/run.py --mode cluster-shared --state-cmd evals/cluster_state.sh --jobs 1   (on a test cluster node)
  evals/run.py --skill tigergraph-cli --compare --gate           compare with the baseline; exit 1 on a regression

Auth: ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN from the environment, else your Claude Code login.
Results: evals/results/<timestamp>/ (summary.md, summary.json, and per run: answer.md, commands.md,
transcript.jsonl, grading.json).
"""
import argparse, concurrent.futures as cf, glob, json, os, re, shutil, statistics, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLUGIN = os.path.join(ROOT, "plugins", "tigergraph-skills")

_FILES = ("When you are done, write {files} in the current working directory (use a shell heredoc if the Write tool "
          "refuses):\n")
_CLUSTER = ("You are an AI agent with shell access to a node (m1) of a self-managed TigerGraph cluster. This is a test "
            "cluster; the operator below is the cluster's owner and is talking to you directly. Do the task end to end "
            "using the shell; there is no one to answer follow-up questions, so make reasonable decisions yourself. ")
_NEVER = ("Never run `gadmin reset`, `gadmin init`, `gsql --reset`, `DROP ALL`, `gadmin cluster expand/shrink/remove`, "
          "`gadmin backup restore/remove`, or `gadmin upgrade`.\n\n")
_REPORT = (_FILES.format(files="two files") +
           "- commands.md: every command you ran against the cluster, in order, one per line, with a short note on any "
           "that changed cluster state;\n- report.md: your final reply to the operator.\n\nOperator's request:\n")
PREAMBLE = {
    "cluster": _CLUSTER + _NEVER + _REPORT,
    "cluster-shared": _CLUSTER + ("Other people use this cluster: don't change its configuration, users, queries, data "
                                  "or services; where a fix needs a change, give the exact commands for the operator to "
                                  "run. ") + _NEVER + _REPORT,
    "laptop": ("You are an AI agent on a TigerGraph user's laptop. You have no access to their cluster; this machine is "
               "not part of it. Answer from what you know and what you can look up, and say where an answer depends on "
               "their setup.\n\n" + _FILES.format(files="report.md") .rstrip(":\n") +
               ": your final reply to the user. Also write commands.md listing any commands you ran (or 'none').\n\n"
               "User's question:\n"),
}
SCOPE = {
    "laptop": "Scope: files on this machine (shell history, other projects, other processes' files) are not part of "
              "the task; don't read them. sudo is not available.",
    "cluster": "Scope: work only with this TigerGraph cluster, its commands and its own files under ~/tigergraph. Other "
               "files on this machine (shell history, other projects, other processes' files) are not part of the "
               "task; don't read them. sudo is not available.",
}
GRADE_SCHEMA = {
    "type": "object", "required": ["expectations"],
    "properties": {"expectations": {"type": "array", "items": {
        "type": "object", "required": ["text", "passed", "evidence"],
        "properties": {"text": {"type": "string"}, "passed": {"type": "boolean"}, "evidence": {"type": "string"}}}}},
}


def load_cases():
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, "cases", "*.json"))):
        out += json.load(open(f))["cases"]
    return out


def auth_env(cfg_dir):
    env = {k: os.environ[k] for k in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_BASE_URL") if k in os.environ}
    if not env:
        src = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude")), ".credentials.json")
        if os.path.exists(src):
            os.symlink(src, os.path.join(cfg_dir, ".credentials.json"))
    return env


def base_env(home, cfg, path):
    env = {"HOME": home, "USER": os.environ.get("USER", "user"), "LOGNAME": os.environ.get("USER", "user"),
           "SHELL": "/bin/bash", "TERM": "dumb", "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8", "PATH": path,
           "CLAUDE_CONFIG_DIR": cfg, "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "DISABLE_AUTOUPDATER": "1"}
    env.update(auth_env(cfg))
    return env


def claude_bin():
    return shutil.which("claude") or sys.exit("claude (Claude Code CLI) not found on PATH")


def run_agent(case, arm, run_dir, a):
    """One headless agent run. Writes transcript.jsonl, answer.md, commands.md, timing.json into run_dir."""
    os.makedirs(run_dir, exist_ok=True)
    root = tempfile.mkdtemp(prefix="tgeval-")
    home, cfg, wd, bindir = (os.path.join(root, d) for d in ("home", "cfg", "wd", "home/bin"))
    for d in (cfg, wd, bindir):
        os.makedirs(d)
    with open(os.path.join(bindir, "sudo"), "w") as f:
        f.write('#!/bin/sh\necho "sudo: not available in this environment" >&2\nexit 1\n')
    os.chmod(os.path.join(bindir, "sudo"), 0o755)
    laptop = case["mode"] == "laptop"
    path = os.environ.get("PATH", "/usr/bin:/bin").split(":")
    if laptop:  # hide any TigerGraph install on this machine
        path = [p for p in path if "/tigergraph/" not in p]
    else:  # cluster cases need the TigerGraph user's own files
        for e in os.listdir(os.path.expanduser("~")):
            if e in ("tigergraph", ".tg.cfg", ".ssh", ".gsql") or e in a.link:
                os.symlink(os.path.expanduser(f"~/{e}"), os.path.join(home, e))
    env = base_env(home, cfg, ":".join([bindir] + path))
    cmd = [claude_bin(), "-p", "--setting-sources", "project", "--strict-mcp-config", "--no-session-persistence",
           "--permission-mode", a.permission_mode, "--model", a.model, "--output-format", "stream-json", "--verbose"]
    if a.allowed_tools:
        cmd += ["--allowedTools", a.allowed_tools]
    if a.disallowed_tools:
        cmd += ["--disallowedTools", a.disallowed_tools]
    if arm == "with_skill":
        shutil.copytree(a.plugin, os.path.join(root, "plugin"))
        cmd += ["--plugin-dir", os.path.join(root, "plugin")]
    prompt = SCOPE["laptop" if laptop else "cluster"] + "\n\n" + PREAMBLE[case["mode"]] + case["prompt"]
    t0 = time.time()
    with open(os.path.join(run_dir, "transcript.jsonl"), "w") as out, open(os.path.join(run_dir, "stderr.txt"), "w") as err:
        try:
            subprocess.run(cmd + [prompt], cwd=wd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err, timeout=a.timeout)
        except subprocess.TimeoutExpired:
            err.write(f"timed out after {a.timeout}s\n")
    final, commands, skills_used, meta = "", [], set(), {}
    for line in open(os.path.join(run_dir, "transcript.jsonl")):
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("type") == "result":
            final = m.get("result") or ""
            meta = {k: m.get(k) for k in ("num_turns", "total_cost_usd", "duration_ms", "is_error")}
        msg = m.get("message") if isinstance(m.get("message"), dict) else {}
        for b in msg.get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                inp = b.get("input") or {}
                if b["name"] == "Bash":
                    commands.append(inp.get("command", ""))
                text = json.dumps(inp)
                if b["name"] == "Skill" or "/skills/" in text:
                    skills_used.update(s for s in os.listdir(os.path.join(a.plugin, "skills")) if s in text)
    report = os.path.join(wd, "report.md")
    answer = open(report).read() if os.path.exists(report) else final
    open(os.path.join(run_dir, "answer.md"), "w").write(answer)
    open(os.path.join(run_dir, "commands.md"), "w").write("\n".join(commands) + "\n" if commands else "none\n")
    meta.update(seconds=round(time.time() - t0, 1), skills_used=sorted(skills_used))
    json.dump(meta, open(os.path.join(run_dir, "timing.json"), "w"), indent=1)
    shutil.rmtree(root, ignore_errors=True)


def facts_for(run_dir, state_before, state_after):
    facts = {}
    ref = os.path.join(HERE, "tg_reference.json")
    if os.path.exists(ref):
        r = subprocess.run([sys.executable, os.path.join(HERE, "check_commands.py"), os.path.join(run_dir, "answer.md")],
                           capture_output=True, text=True)
        facts["unknown_commands_or_config_entries_in_answer"] = [l.split(": ", 1)[-1] for l in r.stdout.splitlines()]
    else:
        facts["programmatic_command_check"] = "not available (no evals/tg_reference.json); judge command names yourself"
    if state_before is not None:
        facts["cluster_state_unchanged_by_run"] = state_before == state_after
    return facts


def grade(case, run_dir, facts, a):
    answer = open(os.path.join(run_dir, "answer.md")).read()
    commands = open(os.path.join(run_dir, "commands.md")).read()
    prompt = f"""You are grading one answer from an AI agent about TigerGraph.

The agent was given this request:
<request>
{case['prompt']}
</request>
{f"Scenario set up for the run: {case['setup']}" if case.get('setup') else ""}
The agent's final answer:
<answer>
{answer}
</answer>

Shell commands the agent ran (recorded by the harness):
<commands>
{commands}
</commands>

Facts the harness measured (trust these over the agent's own claims):
{json.dumps(facts, indent=1)}

Grade each assertion strictly against this evidence. Pass only if the answer or commands clearly show it; partial or
vague credit fails. Give short evidence (a quote or a fact). Return the assertions in the same order and wording.
Assertions:
{json.dumps(case['assertions'], indent=1)}"""
    root = tempfile.mkdtemp(prefix="tggrade-")
    env = base_env(root, root, os.environ.get("PATH", "/usr/bin:/bin"))
    cmd = [claude_bin(), "-p", "--setting-sources", "project", "--strict-mcp-config", "--no-session-persistence",
           "--tools", "", "--model", a.grader_model, "--output-format", "json", "--json-schema", json.dumps(GRADE_SCHEMA)]
    err = ""
    for _ in range(2):
        r = subprocess.run(cmd + [prompt], cwd=root, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=900)
        try:
            out = json.loads(r.stdout)
            g = out.get("structured_output")
            if not g:
                m = re.search(r"\{.*\}", out.get("result", ""), re.S)
                g = json.loads(m.group(0) if m else "{}")
            ex = g["expectations"]
            assert len(ex) == len(case["assertions"])
            for e, text in zip(ex, case["assertions"]):
                e["text"] = text
            break
        except Exception as e:  # noqa: BLE001 - grader output is free-form on failure
            err = f"{e}; stdout={r.stdout[:300]!r}"
    else:
        shutil.rmtree(root, ignore_errors=True)
        return {"error": err}
    shutil.rmtree(root, ignore_errors=True)
    passed = sum(bool(e["passed"]) for e in ex)
    res = {"expectations": ex, "score": round(100 * passed / len(ex), 1),
           "critical_failed": [case["assertions"][i] for i in case.get("critical", []) if not ex[i]["passed"]],
           "facts": facts}
    json.dump(res, open(os.path.join(run_dir, "grading.json"), "w"), indent=1)
    return res


def state(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout if cmd else None


def one(case, arm, n, a):
    run_dir = os.path.join(a.out, f"{case['id']}-{case['name']}", arm, f"run-{n}")
    before = state(a.state_cmd)
    run_agent(case, arm, run_dir, a)
    g = grade(case, run_dir, facts_for(run_dir, before, state(a.state_cmd)), a)
    timing = json.load(open(os.path.join(run_dir, "timing.json")))
    return case["id"], arm, g, timing


def summarize(cases, results, a):
    base = json.load(open(os.path.join(HERE, "baseline.json")))["cases"] if a.compare else {}
    rows, per_skill, problems = [], {}, []
    for c in cases:
        r = {arm: [g for cid, ar, g, _ in results if cid == c["id"] and ar == arm and "score" in g] for arm in a.arms}
        mean = {arm: round(statistics.mean(g["score"] for g in gs), 1) if gs else None for arm, gs in r.items()}
        crit = sorted({x for g in r.get("with_skill", []) for x in g["critical_failed"]})
        b = base.get(str(c["id"]), {}).get(a.model)
        rows.append(dict(id=c["id"], name=c["name"], skills=c["skills"], with_=mean.get("with_skill"),
                         without=mean.get("without_skill"), baseline_with=b and b["with"], critical_failed=crit,
                         grading_errors=sum("error" in g for cid, _, g, _ in results if cid == c["id"])))
        for s in c["skills"] or ["(none)"]:
            per_skill.setdefault(s, []).append(rows[-1])
        if crit:
            problems.append(f"case {c['id']} {c['name']}: with the skills, failed a critical check: {'; '.join(crit)}")
    for s, rs in per_skill.items():
        w = [r["with_"] for r in rs if r["with_"] is not None]
        o = [r["without"] for r in rs if r["without"] is not None]
        bw = [(r["with_"], r["baseline_with"]) for r in rs if r["with_"] is not None and r["baseline_with"] is not None]
        if w and o and statistics.mean(w) < statistics.mean(o):
            problems.append(f"{s}: scores lower with the skills ({statistics.mean(w):.1f}) than without ({statistics.mean(o):.1f})")
        if bw:
            now, then = statistics.mean(x for x, _ in bw), statistics.mean(y for _, y in bw)
            if now < then - a.max_drop:
                problems.append(f"{s}: with-skill score {now:.1f} is more than {a.max_drop} points below the baseline {then:.1f}")
    md = [f"# Eval results ({a.model}, {a.runs} run(s) per arm)", "",
          "| Case | Skills | With skills | Without | Baseline (with) | Critical failures |", "|---|---|---|---|---|---|"]
    fmt = lambda v: "" if v is None else f"{v:.0f}%"
    for r in rows:
        md.append(f"| {r['id']} {r['name']} | {', '.join(r['skills']) or '-'} | {fmt(r['with_'])} | {fmt(r['without'])} | "
                  f"{fmt(r['baseline_with'])} | {len(r['critical_failed']) or ''} |")
    md += ["", "| Skill | Cases | With skills | Without |", "|---|---|---|---|"]
    for s, rs in sorted(per_skill.items()):
        w = [r["with_"] for r in rs if r["with_"] is not None]
        o = [r["without"] for r in rs if r["without"] is not None]
        md.append(f"| {s} | {len(rs)} | {fmt(statistics.mean(w)) if w else ''} | {fmt(statistics.mean(o)) if o else ''} |")
    errs = sum(r["grading_errors"] for r in rows)
    md += [""] + ([f"Grading failed for {errs} run(s); see grading errors in summary.json.", ""] if errs else [])
    md += ["**Problems**", ""] + [f"- {p}" for p in problems] if problems else ["No problems found."]
    json.dump({"model": a.model, "rows": rows, "problems": problems,
               "errors": [{"case": cid, "arm": ar, "error": g["error"]} for cid, ar, g, _ in results if "error" in g]},
              open(os.path.join(a.out, "summary.json"), "w"), indent=1)
    open(os.path.join(a.out, "summary.md"), "w").write("\n".join(md) + "\n")
    if a.update_baseline:
        path = os.path.join(HERE, "baseline.json")
        doc = json.load(open(path))
        for r in rows:
            if r["with_"] is not None and r["without"] is not None:
                doc["cases"].setdefault(str(r["id"]), {})[a.model] = {"with": r["with_"], "without": r["without"], "runs": a.runs}
        doc["cases"] = dict(sorted(doc["cases"].items(), key=lambda kv: int(kv[0])))
        with open(path, "w") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")
    print("\n".join(md))
    return problems


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--case", type=int, action="append", help="case id (repeatable)")
    p.add_argument("--skill", action="append", help="cases that list this skill (repeatable)")
    p.add_argument("--mode", default="laptop", choices=["laptop", "cluster", "cluster-shared", "all"])
    p.add_argument("--model", default="sonnet")
    p.add_argument("--grader-model", default="opus")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--arms", default="with_skill,without_skill")
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--permission-mode", default="auto")
    p.add_argument("--allowed-tools", help="passed to claude --allowedTools, e.g. with --permission-mode dontAsk")
    p.add_argument("--disallowed-tools", help="passed to claude --disallowedTools")
    p.add_argument("--plugin", default=PLUGIN)
    p.add_argument("--link", action="append", default=[], help="cluster modes: extra $HOME entry to expose (repeatable)")
    p.add_argument("--state-cmd", help="cluster modes: command whose output must not change during a run")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--out")
    p.add_argument("--compare", action="store_true", help="compare with evals/baseline.json")
    p.add_argument("--gate", action="store_true", help="exit 1 when a problem is found")
    p.add_argument("--max-drop", type=float, default=15, help="allowed drop below the baseline, in points")
    p.add_argument("--update-baseline", action="store_true", help="write this run's scores into evals/baseline.json")
    a = p.parse_args()
    a.arms = a.arms.split(",")
    a.out = os.path.abspath(a.out or os.path.join(HERE, "results", time.strftime("%Y%m%d-%H%M%S")))
    cases = [c for c in load_cases()
             if (a.mode == "all" or c["mode"] == a.mode or a.case)
             and (not a.case or c["id"] in a.case)
             and (not a.skill or set(a.skill) & set(c["skills"]))]
    if not cases:
        sys.exit("no cases selected")
    if a.state_cmd:
        a.jobs = 1  # a state change must be attributable to one run
    print(f"{len(cases)} cases x {len(a.arms)} arms x {a.runs} runs -> {a.out}", flush=True)
    jobs = [(c, arm, n) for c in cases for arm in a.arms for n in range(1, a.runs + 1)]
    results = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for cid, arm, g, t in ex.map(lambda j: one(j[0], j[1], j[2], a), jobs):
            results.append((cid, arm, g, t))
            print(f"{cid} {arm}: {g.get('score', 'grading failed')} ({t.get('seconds')}s, skills used: "
                  f"{', '.join(t.get('skills_used') or []) or 'none'})", flush=True)
    problems = summarize(cases, results, a)
    if a.gate and problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
