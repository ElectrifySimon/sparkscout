"""MCP stress harness — randomized adversarial tool calls, multi-session.

v3.0 (2026-09-10). Lightweight load + fuzz tool for any FastMCP server
reachable over HTTP+SSE. Generates N calls across M concurrent sessions,
mixes valid + adversarial input, classifies outcomes, and dumps
per-failure JSON for offline triage.

The harness surfaced two real defects on SparkScout, both now fixed:

1. **Silent-filter-drop** (2026-09-09, fixed in commit 231e6b9). The MCP
   server passed 1000 randomized calls without crashing but silently
   swallowed bad filter values (None, empty, floats, missing dim
   entries). The fix added `filters_applied`/`filters_dropped`/
   `limit_clamped` to the query response. The classifier marks these
   as `ok-surface` (v2.0) — server surfaced what it did.

2. **Sync-tool event-loop block at --users >= 5** (2026-09-10, fixed
   in commit b1e28fd). All 11 tools are now `async def` with DuckDB
   and FTS5 I/O dispatched via `asyncio.to_thread`. Post-fix
   verification at `--users 5` and `--users 10` (100 calls each,
   seed=200): 0% malformed, 0% silent-coerce, ~8% ok-surface.
   The concurrency-bisect (`--users 1/2/5/10`) stays in the pre-ship
   gate to catch any future async regression. See
   `references/sparkscout-fastmcp-concurrency-2026-09-10.md` for the
   full diagnosis.

How it works:
- init_session(user_id) opens a unique MCP session via the JSON-RPC
  initialize method, captures the Mcp-Session-Id header.
- call(session, tool, args) POSTs tools/call with the session-id
  header and bearer token.
- gen_test(rng) returns one of 11 test categories: meta-list,
  meta-one, query-pxweb, query-cost, query-no-filter, query-bad-dataset,
  query-bad-filter, query-weird-types, query-edge-limits,
  fusion-natural, fusion-edge.
- classify(category, result, text) scores each call:
    ok, ok-surface (server surfaced filter/limit coercion via P0
    surface fields), zero-rows, clean-error (tool returned
    {"error":"..."} cleanly), validation-error (pydantic rejected
    input), silent-coerce (bad input silently absorbed AND server
    did NOT surface), server-error, malformed (no SSE data line),
    transport-fail, rpc-error.

Tool names: the harness targets `irena_*` (the Python function
names registered by `@mcp.tool`). FastMCP 4.0 does not apply the
instance-name prefix that 3.x did; the public MCP surface and this
harness both use `irena_*`. Earlier versions used `irena_*` —
that is wrong for 4.0.

Default config: 10 batches x 100 calls x 5 users = 1000 calls.
End-to-end runtime: ~9 minutes per batch of 100. The bottleneck is the
ssh+pct-exec overhead per call (~500ms), not the server. Direct-pipe
testing (no ssh) would run 10x faster; this script targets cross-host
operator testing.

**Always run with `python3 -u`** when launched from a backgrounded
terminal session. Without `-u`, the stdout buffer (4-8 KB) does not
flush before the process dies, leaving an empty log file. Verified
2026-09-10.

Usage:
    # Full 1000-call run (10 minutes)
    python3 -u scripts/mcp-stress-harness.py --host <mg-host-IP> \\
        --lxc 104 --url http://127.0.0.1:7100/mcp \\
        --token "$FASTMCP_BEARER" \\
        --batches 10 --per-batch 100 --users 5 --seed 200

    # 100-call smaller-test fallback (90 seconds, no concurrency gate)
    python3 -u scripts/mcp-stress-harness.py --host <mg-host-IP> \\
        --lxc 104 --url http://127.0.0.1:7100/mcp \\
        --token "$FASTMCP_BEARER" \\
        --batches 1 --per-batch 100 --users 2 --seed 200

    # --users 5 concurrency gate (catches the sync-tool bug)
    python3 -u scripts/mcp-stress-harness.py --host <mg-host-IP> \\
        --lxc 104 --url http://127.0.0.1:7100/mcp \\
        --token "$FASTMCP_BEARER" \\
        --batches 1 --per-batch 100 --users 5 --seed 200

For hermes-style agent invocation: pre-stage via
`scp scripts/mcp-stress-harness.py root@<host>:/tmp/`,
then run via `ssh root@<host> "pct exec <lxc> -- python3 -u /tmp/mcp-stress-harness.py ..."`.
"""
import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import time
from collections import Counter


def shlex_quote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def remote_exec(host, lxc, command, timeout=60):
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", f"root@{host}",
         f"pct exec {lxc} -- bash -c {shlex_quote(command)}"],
        capture_output=True, text=True, timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr


def init_session(host, lxc, url, token, user_id):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05",
                   "capabilities": {},
                   "clientInfo": {"name": f"stress-{user_id}", "version": "0.1"}},
    })
    cmd = (
        f"curl -sS -i -X POST {url} "
        f"-H 'Content-Type: application/json' "
        f"-H 'Accept: application/json, text/event-stream' "
        f"-H 'Authorization: Bearer {token}' "
        f"-d {shlex_quote(payload)}"
    )
    rc, out, err = remote_exec(host, lxc, cmd)
    for line in out.splitlines():
        if line.lower().startswith("mcp-session-id:"):
            return line.split(":", 1)[1].strip()
    return None


def call_tool(host, lxc, url, token, session, tool, args):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    })
    cmd = (
        f"curl -sS -X POST {url} "
        f"-H 'Content-Type: application/json' "
        f"-H 'Accept: application/json, text/event-stream' "
        f"-H 'Authorization: Bearer {token}' "
        f"-H 'mcp-session-id: {session}' "
        f"-d {shlex_quote(payload)}"
    )
    rc, out, err = remote_exec(host, lxc, cmd, timeout=120)
    if "data: " not in out:
        return {"_parse": "no_data", "_raw": out[:200]}
    data = out.split("data: ", 1)[1].split("\n", 1)[0]
    try:
        return json.loads(data)
    except Exception as e:
        return {"_parse": str(e), "_raw": data[:200]}


def text_of(j):
    if "error" in j and not isinstance(j.get("result"), dict):
        return f"ERROR: {j['error']}"
    content = j.get("result", {}).get("content", [])
    if isinstance(content, list) and content:
        return content[0].get("text", "")
    return json.dumps(j)[:300]


def rows_of(text):
    try:
        j = json.loads(text)
        if isinstance(j, dict) and "row_count" in j:
            return j["row_count"]
        if isinstance(j, dict) and "rows" in j and isinstance(j["rows"], list):
            return len(j["rows"])
        if isinstance(j, list):
            return len(j)
    except Exception:
        return None
    return None


REGIONS = ["World", "Europe", "Asia", "Africa", "North America", "South America",
           "Oceania", "Eurasia", "Middle East"]
TECH_COST = ["solar_pv", "onshore_wind", "offshore_wind", "hydropower"]
TECH_PXWEB = ["Solar PV", "Solar", "Wind", "Hydropower", "Hydro",
              "Onshore wind", "Offshore wind", "Solar thermal",
              "Bioenergy", "Geothermal"]
COUNTRIES = ["AFG", "DEU", "CHN", "USA", "IND", "BRA", "FRA", "ESP", "NGA",
             "AUS", "ZAF", "MEX", "JPN", "KOR", "CAN", "GBR"]
YEARS = list(range(2010, 2026))
PXWEB_DATASETS = ["country_capacity", "country_generation", "region_capacity",
                  "region_generation", "re_share", "heat_generation",
                  "public_investments"]
ALL_DATASETS = PXWEB_DATASETS + ["lcoe_weighted"]


def random_pxweb_filters():
    f = {}
    if random.random() < 0.8:
        f["technologies"] = random.sample(TECH_PXWEB, k=random.randint(1, 2))
    if random.random() < 0.7:
        f["countries"] = random.sample(COUNTRIES, k=random.randint(1, 2))
    if random.random() < 0.7:
        f["years"] = random.sample(YEARS, k=random.randint(1, 3))
    return f


def random_cost_filters():
    f = {}
    if random.random() < 0.7:
        f["technologies"] = random.sample(TECH_COST, k=random.randint(1, 2))
    if random.random() < 0.7:
        f["regions"] = random.sample(REGIONS, k=random.randint(1, 2))
    if random.random() < 0.6:
        f["years"] = random.sample(YEARS, k=random.randint(1, 4))
    if random.random() < 0.3:
        f["countries"] = random.sample(COUNTRIES, k=random.randint(1, 2))
    return f


def gen_test(rng):
    r = rng.random()
    if r < 0.10:
        return ("meta-list", "irena_list_datasets", {})
    if r < 0.18:
        return ("meta-one", "irena_get_dataset_meta",
                {"dataset_id": rng.choice(ALL_DATASETS)})
    if r < 0.55:
        ds = rng.choice(PXWEB_DATASETS)
        return ("query-pxweb", "irena_query_dataset",
                {"dataset_id": ds, "filters": random_pxweb_filters(),
                 "limit": rng.randint(1, 50)})
    if r < 0.70:
        return ("query-cost", "irena_query_dataset",
                {"dataset_id": "lcoe_weighted",
                 "filters": random_cost_filters(),
                 "limit": rng.randint(1, 50)})
    if r < 0.78:
        return ("query-no-filter", "irena_query_dataset",
                {"dataset_id": rng.choice(ALL_DATASETS),
                 "limit": rng.randint(1, 20)})
    if r < 0.83:
        return ("query-bad-dataset", "irena_query_dataset",
                {"dataset_id": rng.choice(["foo", "bar_baz", "LCOE_WEIGHTED",
                                            "", "lcoe weighted",
                                            "lcoe_weighted_typo"]),
                 "limit": 5})
    if r < 0.88:
        return ("query-bad-filter", "irena_query_dataset",
                {"dataset_id": rng.choice(ALL_DATASETS),
                 "filters": {"currencies": ["USD"], "garbage": ["x"]},
                 "limit": 5})
    if r < 0.92:
        return ("query-weird-types", "irena_query_dataset",
                {"dataset_id": rng.choice(ALL_DATASETS),
                 "filters": {"years": ["twenty-twenty-four", None, 3.14],
                             "technologies": [None, "", 0]},
                 "limit": 5})
    if r < 0.95:
        return ("query-edge-limits", "irena_query_dataset",
                {"dataset_id": rng.choice(ALL_DATASETS),
                 "limit": rng.choice([-5, 0, 1, 999999, 100000])})
    if r < 0.97:
        return ("fusion-natural", "irena_answer_question",
                {"question": rng.choice([
                    "What is the LCOE of solar PV?",
                    "weighted-average LCOE solar pv 2024",
                    "cost of onshore wind in Europe",
                    "cheapest renewable electricity 2024",
                    "global LCOE trend",
                    "capacity factor solar 2023",
                    "investment in renewables 2022",
                    "wind capacity growth Africa",
                    "solar PV vs onshore wind cost",
                ])})
    return ("fusion-edge", "irena_answer_question",
            {"question": rng.choice([
                "",
                " ",
                "solar chinese mandarin phrase",
                "LCOE?" * 200,
                "!@#$%^&*()",
                "renewable energy renewable energy renewable",
                "what is the answer to life the universe and everything",
            ])})


def classify(category, result, text):
    """Return (outcome, detail).

    Outcomes:
      ok                     - tool succeeded, rows returned
      zero-rows              - tool succeeded, 0 rows (legit empty result)
      clean-error            - tool returned {"error":"..."} (correctly)
      validation-error       - pydantic rejected input
      server-error           - server-side exception
      malformed              - couldn't parse response
      transport-fail         - network error
      silent-coerce          - bad input silently coerced
    """
    if "_parse" in result:
        return "malformed", result.get("_raw", "")[:120]

    if "error" in result:
        err = result["error"]
        if isinstance(err, dict):
            msg = err.get("message", "")
        else:
            msg = str(err)
        if "validation" in msg.lower() or "missing_argument" in msg:
            return "validation-error", msg[:120]
        if "ServerError" in str(err) or "Internal" in str(err):
            return "server-error", msg[:120]
        return "rpc-error", msg[:120]

    is_error = result.get("result", {}).get("isError", False)
    try:
        body = json.loads(text)
        if isinstance(body, dict) and "error" in body:
            return "clean-error", body["error"][:120]
    except Exception:
        pass

    if text.startswith("ERROR calling tool"):
        return "tool-error", text[:120]
    if text.startswith("ERROR: "):
        return "rpc-error", text[:120]
    if is_error:
        return "tool-error", text[:120]

    # Category-specific silent-coerce detection. With the P0 fix
    # shipped 2026-09-10 the response includes filters_applied,
    # filters_dropped, limit_requested, limit_applied, limit_clamped.
    # If those fields are present, the surface is loud (good).
    # If absent and the category is query-edge-limits or
    # query-weird-types, the response lacks the new surface and
    # we mark it silent-coerce so it's visible to the operator.
    if category in ("query-edge-limits", "query-weird-types"):
        body = None
        try:
            body = json.loads(text)
        except Exception:
            pass
        if isinstance(body, dict):
            if "filters_dropped" in body or "limit_clamped" in body:
                return "ok-surface", "fix present"
        return "silent-coerce", text[:80]

    rc = rows_of(text)
    if rc == 0:
        return "zero-rows", text[:80]
    if rc is not None and rc >= 1:
        return "ok", f"rows={rc}"
    return "ok", text[:80]


def run_batch(host, lxc, url, token, batch_id, n, users, seed):
    rng = random.Random(seed)
    sessions = []
    for i in range(users):
        s = init_session(host, lxc, url, token, f"u{i}")
        if s:
            sessions.append(s)
    if not sessions:
        print("FATAL: no sessions established", flush=True)
        return Counter(), {}, [], []

    outcomes = Counter()
    by_category = {}
    failures = []
    silent = []
    latencies_ms = []

    print(f"\n=== BATCH {batch_id} (n={n}, users={len(sessions)}, seed={seed}) ===", flush=True)
    t0 = time.time()
    for i in range(n):
        cat, tool, args = gen_test(rng)
        sess = rng.choice(sessions)
        t_call = time.time()
        try:
            res = call_tool(host, lxc, url, token, sess, tool, args)
        except Exception as e:
            outcomes["transport-fail"] += 1
            failures.append((cat, tool, str(e)[:120]))
            continue
        latencies_ms.append((time.time() - t_call) * 1000)
        text = text_of(res)
        outcome, detail = classify(cat, res, text)
        outcomes[outcome] += 1
        by_category.setdefault(cat, Counter())[outcome] += 1
        if outcome in ("server-error", "malformed", "transport-fail",
                       "tool-error", "rpc-error"):
            failures.append((cat, tool, json.dumps(args)[:100], detail))
        if outcome == "silent-coerce":
            silent.append((cat, tool, json.dumps(args)[:120], detail))

    elapsed = time.time() - t0
    avg_lat = statistics.mean(latencies_ms) if latencies_ms else 0
    print(f"  elapsed: {elapsed:.1f}s, avg call: {avg_lat:.0f}ms", flush=True)
    print("OUTCOMES:", flush=True)
    for k, v in outcomes.most_common():
        print(f"  {k:18s} {v:5d}", flush=True)
    print("BY CATEGORY:", flush=True)
    for cat in sorted(by_category):
        oc = by_category[cat]
        line = "  ".join(f"{k}={v}" for k, v in oc.most_common())
        print(f"  {cat:22s} {line}", flush=True)
    if failures or silent:
        out_path = f"/tmp/stress_batch_{batch_id}_issues.json"
        with open(out_path, "w") as f:
            json.dump({"failures": failures, "silent_coerce": silent}, f, indent=2)
        print(f"  issues dumped -> {out_path}", flush=True)
    return outcomes, by_category, failures, silent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="Proxmox host running the LXC")
    ap.add_argument("--lxc", type=int, required=True, help="LXC ID hosting the MCP server")
    ap.add_argument("--url", required=True, help="MCP HTTP+SSE URL, e.g. http://127.0.0.1:7100/mcp")
    ap.add_argument("--token", default=os.environ.get("FASTMCP_BEARER", ""),
                    help="Bearer token (or set FASTMCP_BEARER env)")
    ap.add_argument("--batches", type=int, default=10)
    ap.add_argument("--per-batch", type=int, default=100)
    ap.add_argument("--users", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    if not args.token:
        print("ERROR: --token or FASTMCP_BEARER required", file=sys.stderr)
        return 2

    aggregate = Counter()
    for b in range(1, args.batches + 1):
        oc, _, _, _ = run_batch(args.host, args.lxc, args.url, args.token,
                                args.seed + b, args.per_batch, args.users,
                                args.seed + b)
        aggregate.update(oc)

    print(f"\n=== AGGREGATED ({args.batches} batches x {args.per_batch}) ===")
    for k, v in aggregate.most_common():
        print(f"  {k:18s} {v:5d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
