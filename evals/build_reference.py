"""Build tg_reference.json from a TigerGraph install: gadmin subcommands, config entries, gcollect components.

Run on a node of a released TigerGraph version (not a development build) as the TigerGraph OS user.
"""
import json
import re
import subprocess


def gadmin_subcommands(args):
    out = subprocess.run(["gadmin", *args, "--help"], capture_output=True, text=True).stdout
    m = re.search(r"Available Commands:\n(.*?)\n\n", out, re.S)
    return [line.split()[0] for line in m.group(1).splitlines()] if m else []


version = subprocess.run(["gadmin", "version"], capture_output=True, text=True).stdout.split("\n")[0]
entries = subprocess.run(["gadmin", "config", "list", "entry"], capture_output=True, text=True).stdout
gcollect = subprocess.run(["gcollect", "-h"], capture_output=True, text=True).stdout
ref = {
    "source": version.strip(),
    "gadmin": {c: gadmin_subcommands([c]) for c in gadmin_subcommands([])},
    "config_entries": sorted({line.split()[0] for line in entries.splitlines() if line.strip()}),
    "gcollect_components": re.search(r"Supported components: (\S+)", gcollect).group(1).split(","),
}
json.dump(ref, open("tg_reference.json", "w"), indent=1)
print(f"wrote tg_reference.json from {ref['source']}")
