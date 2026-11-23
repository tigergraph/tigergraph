#!/bin/bash
# Print the cluster state a read-only eval run must leave unchanged: service status, staged config, backups,
# users, and per graph its schema/jobs/queries and vertex/edge counts. Run as the TigerGraph OS user on a node.
# Used as: evals/run.py --mode cluster-shared --state-cmd evals/cluster_state.sh
set -u
echo "## status"; gadmin status 2>&1 | grep -E '^\|' | grep -v 'Service Name' | awk -F'|' '{gsub(/ /,"",$2);gsub(/ /,"",$3);print $2, $3}'
echo "## staged config"; gadmin config diff 2>&1 | grep -vE '^\s*$'
echo "## backups"; gadmin backup list 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep -E '^\|' | grep -v TAG | awk -F'|' '{gsub(/ /,"",$2);print $2}'
echo "## users"; gsql 'SHOW USER' 2>&1 | grep -oE 'Name: [^ ]+' | sort
echo "## global"; gsql ls 2>&1 | grep -vE '^\s*$' | md5sum
P=$(gadmin config get Nginx.Port 2>/dev/null | tail -1); H=$(gmyip 2>/dev/null || hostname -i)
for g in $(gsql ls 2>&1 | sed -n 's/^ *- Graph \([A-Za-z0-9_]*\)(.*/\1/p'); do
  echo "## graph $g"; gsql -g "$g" ls 2>&1 | grep -vE '^\s*$' | md5sum
  for f in vertex edge; do
    curl -s -m 30 -X POST "http://$H:$P/restpp/builtins/$g?realtime=true" -d "{\"function\":\"stat_${f}_number\",\"type\":\"*\"}" \
      | python3 -c 'import json,sys
try: print(",".join(sorted("%s=%s" % (r.get("v_type") or r.get("e_type"), r["count"]) for r in json.load(sys.stdin)["results"])))
except Exception: print("counts unavailable")'
  done
done
