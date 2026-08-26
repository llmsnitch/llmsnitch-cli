"""Per-AI network tracking — remote hosts + MB throughput, sampled live.

We use `nettop -P -L 1 -J bytes_in,bytes_out -x` to get per-PID cumulative
byte counters, and `lsof -i -p <pid>` for the list of remote endpoints.
Both results are attributed to the AI bucket the PID belongs to, using the
same classifier as the subprocs pane. Cumulative bytes are differenced
against the previous sample so we report DELTAS per tick, plus a running
session-total.
"""

import subprocess
from collections import Counter

from fs_coil.runtime import _running_actor_detail

_NETTOP_PREV    = {}   # {pid: (bytes_in, bytes_out)} — previous sample
_NET_SESSION    = {"vscode_claude": {"bytes_in": 0, "bytes_out": 0,
                                     "hosts":   Counter()},
                   "claude_app":    {"bytes_in": 0, "bytes_out": 0,
                                     "hosts":   Counter()},
                   "opencode":      {"bytes_in": 0, "bytes_out": 0,
                                     "hosts":   Counter()}}


def _nettop_snapshot():
    """Return {pid: (bytes_in, bytes_out)} cumulative since-boot counters."""
    try:
        r = subprocess.run(
            ["/usr/bin/nettop", "-P", "-L", "1", "-x", "-J",
             "bytes_in,bytes_out"],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return {}
    out = {}
    for line in r.stdout.splitlines():
        parts = line.split(",")
        if len(parts) < 3:
            continue
        label, bi_s, bo_s = parts[0], parts[1], parts[2]
        dot = label.rfind(".")
        if dot < 0:
            continue
        try:
            pid = int(label[dot + 1:])
            out[pid] = (int(bi_s), int(bo_s))
        except ValueError:
            continue
    return out


def _lsof_remote_hosts(pid):
    """Return list of remote 'host:port' strings for TCP endpoints owned by
    pid. Best-effort, 1s timeout."""
    if not pid:
        return []
    try:
        r = subprocess.run(
            ["/usr/sbin/lsof", "-nP", "-iTCP", "-sTCP:ESTABLISHED",
             "-a", "-p", str(pid)],
            capture_output=True, text=True, timeout=1,
        )
    except Exception:
        return []
    hosts = []
    for ln in r.stdout.splitlines()[1:]:
        # NAME column is the last token: 1.2.3.4:443->5.6.7.8:443
        parts = ln.split()
        if not parts:
            continue
        name = parts[-1]
        if "->" in name:
            remote = name.split("->", 1)[1]
            hosts.append(remote)
    return hosts


def _sample_network():
    """One sampling round: update _NET_SESSION deltas + host counters.
    Returns the per-bucket current snapshot for rendering."""
    agg = _running_actor_detail()
    net = _nettop_snapshot()

    by_bucket = {
        "vscode_claude": {"bytes_in": 0, "bytes_out": 0, "hosts": Counter()},
        "claude_app":    {"bytes_in": 0, "bytes_out": 0, "hosts": Counter()},
        "opencode":      {"bytes_in": 0, "bytes_out": 0, "hosts": Counter()},
    }

    for bucket, info in agg.items():
        for p in info.get("procs", []):
            pid = p["pid"]
            bi_now, bo_now = net.get(pid, (0, 0))
            prev = _NETTOP_PREV.get(pid)
            if prev and (bi_now >= prev[0] and bo_now >= prev[1]):
                d_in  = bi_now - prev[0]
                d_out = bo_now - prev[1]
                by_bucket[bucket]["bytes_in"]  += d_in
                by_bucket[bucket]["bytes_out"] += d_out
                _NET_SESSION[bucket]["bytes_in"]  += d_in
                _NET_SESSION[bucket]["bytes_out"] += d_out
            _NETTOP_PREV[pid] = (bi_now, bo_now)
            # Remote hosts: sample lsof for CPU-heavy PIDs only to avoid
            # spawning N lsofs every tick. >0.1% CPU is "probably talking".
            if p["cpu"] > 0.1:
                for h in _lsof_remote_hosts(pid):
                    by_bucket[bucket]["hosts"][h] += 1
                    _NET_SESSION[bucket]["hosts"][h] += 1
    return by_bucket
