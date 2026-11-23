"""Check that gadmin subcommands, config entries and gcollect components named in Markdown files exist.

Usage: python3 evals/check_commands.py <file.md>...   (needs evals/tg_reference.json; see build_reference.py)
"""
import json
import pathlib
import re
import sys

ref = json.load(open(pathlib.Path(__file__).with_name("tg_reference.json")))
# subcommands whose next word is a service, path or command rather than a child subcommand
FREE_ARGS = {"status", "log", "start", "stop", "restart", "run", "metric", "reset", "init", "upgrade"}


def problems(text):
    text = re.sub(r"\s#\s.*", "", text)  # drop shell comments
    found = []
    for m in re.finditer(r"\bgadmin\s+([a-z]+)(?:\s+([a-z][a-z-]*))?", text):
        sub, child = m.groups()
        if sub not in ref["gadmin"]:
            found.append(f"unknown gadmin subcommand: gadmin {sub}")
        elif ref["gadmin"][sub] and child and sub not in FREE_ARGS and child not in ref["gadmin"][sub]:
            found.append(f"unknown gadmin subcommand: gadmin {sub} {child}")
    for m in re.finditer(r"gadmin\s+config\s+(?:get|set)\s+([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+)", text):
        if m.group(1) not in ref["config_entries"]:
            found.append(f"unknown config entry: {m.group(1)}")
    for m in re.finditer(r"gcollect[^\n`]*?\s-c\s+([A-Za-z0-9_,.-]+)", text):
        found += [f"unknown gcollect component: {c}" for c in m.group(1).split(",") if c and c not in ref["gcollect_components"]]
    return sorted(set(found))


failed = False
for path in sys.argv[1:]:
    for p in problems(open(path).read()):
        print(f"{path}: {p}")
        failed = True
sys.exit(1 if failed else 0)
