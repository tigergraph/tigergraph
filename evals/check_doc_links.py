#!/usr/bin/env python3
"""Check that every docs page a skill names resolves on the published TigerGraph docs site.
Usage: check_doc_links.py [--version 4.3] <file.md>...   Exits 1 if any page returns non-200."""
import re, sys, urllib.error, urllib.request

args = sys.argv[1:]
version = "4.3"
if args[:1] == ["--version"]:
    version, args = args[1], args[2:]
BASE = f"https://www.tigergraph.com/docs/tigergraph-server/{version}/"
# docs page paths look like `section/page`; skip repo-relative paths
PAGE = re.compile(r"`((?:installation|cluster-and-ha-management|backup-and-restore|reference|security|system-management|"
                  r"troubleshooting|gsql-shell|intro|data-loading|user-access|API)/[a-z0-9/-]*)`")
FULL = re.compile(r"https://www\.tigergraph\.com/docs/[^\s`)<>]+(?![^\s`]*<)")  # skip templates like .../<version>/<page>

GSQL = re.compile(r"`((?:ddl-and-loading|querying|appendix)/[a-z0-9/-]*)`")
GBASE = f"https://www.tigergraph.com/docs/gsql-ref/{version}/"
urls = set()
for f in args:
    text = open(f).read()
    urls |= {BASE + p for p in PAGE.findall(text)}
    urls |= {GBASE + p for p in GSQL.findall(text)}
    urls |= {u for u in FULL.findall(text) if "<" not in u}

bad = 0
for u in sorted(urls):
    try:
        req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "doc-link-check"})
        code = urllib.request.urlopen(req, timeout=20).status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # network trouble is not a broken link
        print(f"?? {u} ({e})"); continue
    if code != 200:
        bad += 1; print(f"{code} {u}")
print(f"{len(urls)} pages checked, {bad} broken")
sys.exit(1 if bad else 0)
