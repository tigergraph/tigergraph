#!/usr/bin/env python3
"""Check every SKILL.md against the Agent Skills format (agentskills.io) that Codex, Cursor, Copilot and others load.

Usage: check_skills.py   exits 1 on a problem.
"""
import glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
LIMITS = {"name": 64, "description": 1024, "compatibility": 500}

errs = []
for path in sorted(glob.glob(f"{ROOT}/plugins/*/skills/*/SKILL.md")):
    rel = os.path.relpath(path, ROOT)
    text = open(path).read()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        errs.append(f"{rel}: no YAML frontmatter")
        continue
    fields = dict(re.findall(r"^([a-z-]+):[ \t]*(.*)$", m.group(1), re.M))
    for k in sorted(set(fields) - ALLOWED):
        errs.append(f"{rel}: field '{k}' is not part of the Agent Skills format")
    for k in ("name", "description"):
        if not fields.get(k):
            errs.append(f"{rel}: missing {k}")
    for k, n in LIMITS.items():
        if len(fields.get(k, "")) > n:
            errs.append(f"{rel}: {k} is {len(fields[k])} characters; the limit is {n}")
    name, folder = fields.get("name", ""), os.path.basename(os.path.dirname(path))
    if name != folder:
        errs.append(f"{rel}: name '{name}' must match the folder name '{folder}'")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        errs.append(f"{rel}: name must be lowercase letters, digits and single hyphens")
    for ref in re.findall(r"`(references/[^`]+\.md)`", text):
        if not os.path.exists(os.path.join(os.path.dirname(path), ref)):
            errs.append(f"{rel}: links to missing {ref}")

for e in errs:
    print(e, file=sys.stderr)
sys.exit(1 if errs else 0)
