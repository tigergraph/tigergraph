#!/usr/bin/env python3
"""Check the eval cases, and that a change to a skill comes with a new or updated case for it.

Usage:
  validate.py                      check every file in evals/cases/
  validate.py --changed-since REF  also require, for each skill changed since REF, a case for that skill
                                   that is new or changed since REF
"""
import glob, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = "evals/cases"
MODES = ("laptop", "cluster", "cluster-shared")
DUPLICATES = []
FIELDS = {"id", "name", "skills", "mode", "prompt", "assertions", "critical", "setup", "notes"}


def skills():
    return {os.path.basename(os.path.dirname(p)) for p in glob.glob(f"{ROOT}/plugins/*/skills/*/SKILL.md")}


def load_cases(read):
    """read(relpath) -> text or None. Returns {id: (file, case)}."""
    out = {}
    for rel in read("__list__"):
        text = read(rel)
        if text is None:
            continue
        for c in json.loads(text).get("cases", []):
            if c.get("id") in out:
                DUPLICATES.append(f"{rel} case {c.get('id')}: id also used in {out[c.get('id')][0]}")
            out[c.get("id")] = (rel, c)
    return out


def worktree_reader(rel):
    if rel == "__list__":
        return sorted(os.path.relpath(p, ROOT) for p in glob.glob(f"{ROOT}/{CASES}/*.json"))
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()


def git_reader(ref):
    def read(rel):
        if rel == "__list__":
            r = subprocess.run(["git", "ls-tree", "--name-only", ref, f"{CASES}/"], cwd=ROOT, capture_output=True, text=True)
            return [l for l in r.stdout.split() if l.endswith(".json")]
        r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=ROOT, capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None
    return read


def check(cases, known):
    errs, names = [], {}
    for cid, (rel, c) in cases.items():
        where = f"{rel} case {cid}"
        stem = os.path.splitext(os.path.basename(rel))[0]
        if not isinstance(cid, int) or cid <= 0:
            errs.append(f"{where}: id must be a positive integer")
        for k in ("name", "prompt"):
            if not isinstance(c.get(k), str) or not c[k].strip():
                errs.append(f"{where}: missing {k}")
        if isinstance(c.get("name"), str):
            if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", c["name"]):
                errs.append(f"{where}: name must be kebab-case")
            if c["name"] in names:
                errs.append(f"{where}: name also used by case {names[c['name']]}")
            names[c["name"]] = cid
        if set(c) - FIELDS:
            errs.append(f"{where}: unknown fields {sorted(set(c) - FIELDS)}")
        if c.get("mode") not in MODES:
            errs.append(f"{where}: mode must be one of {', '.join(MODES)}")
        sk = c.get("skills")
        if not isinstance(sk, list) or any(s not in known for s in sk):
            errs.append(f"{where}: skills must list existing skills ({', '.join(sorted(known))})")
        elif stem != "general" and stem not in sk:
            errs.append(f"{where}: a case in {stem}.json must list {stem} in skills")
        elif stem == "general" and sk:
            errs.append(f"{where}: general.json is for cases no single skill owns; move it to {sk[0]}.json")
        a = c.get("assertions")
        if not isinstance(a, list) or not a or not all(isinstance(x, str) and x.strip() for x in a):
            errs.append(f"{where}: assertions must be a non-empty list of strings")
        crit = c.get("critical", [])
        if not isinstance(crit, list) or any(not isinstance(i, int) or not 0 <= i < len(a or []) for i in crit):
            errs.append(f"{where}: critical must list assertion indexes")
    return errs


def changed_skills(ref):
    r = subprocess.run(["git", "diff", "--name-only", f"{ref}...HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    return sorted({m.group(1) for p in r.stdout.split() for m in [re.match(r"plugins/[^/]+/skills/([^/]+)/", p)] if m})


def main():
    args = sys.argv[1:]
    known = skills()
    cases = load_cases(worktree_reader)
    errs = DUPLICATES + check(cases, known)
    ids = [c["id"] for _, c in cases.values()]
    if "--changed-since" in args:
        ref = args[args.index("--changed-since") + 1]
        old = load_cases(git_reader(ref))
        DUPLICATES.clear()
        touched = [c for cid, (_, c) in cases.items() if cid not in old or old[cid][1] != c]
        for s in changed_skills(ref):
            if s in known and not any(s in c.get("skills", []) for c in touched):
                errs.append(f"skill {s} changed but no case in {CASES}/ that lists it was added or updated. "
                            f"Add one that fails without the change and passes with it (see evals/README.md).")
    for e in errs:
        print(e, file=sys.stderr)
    if errs:
        sys.exit(1)
    print(f"{len(ids)} cases OK")


if __name__ == "__main__":
    main()
