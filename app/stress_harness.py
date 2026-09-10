"""Stress harness: randomised MCP tool calls across multiple sessions.

Generates 10 batches x 100 = 1000 tool calls. Mixes valid + adversarial input.
Logs failures with category tags. Reports aggregated feedback.

Usage:
  python3 stress.py --batch 1
  python3 stress.py --batches 10
"""
import argparse
import json
import random
import subprocess
import sys
import time
from collections import Counter

BEARER = "f053f2b2676f6f4dacabeb5e46d6d8bffcef6aece752634adebfc72a2391fbce"
HOST = "http://127.0.0.1:7100/mcp"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def host(cmd: str) -> str:
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", "root@192.168.0.171",
         f"pct exec 104 -- {cmd}"],
        capture_output=True, text=True, timeout=60,
    )
    return r.stdout


def init_session(user_id: str) -> str:
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05",
                   "capabilities": {},
                   "clientInfo": {"name": f"stress-{user_id}", "version": "1.0"}},
    })
    out = host(
        f"curl -sS -i -X POST {HOST} "
        f"-H \"Content-Type: application/json\" "
        f"-H \"Accept: application/json, text/event-stream\" "
        f"-H \"Authorization: Bearer {BEARER}\" -d " + repr(payload)
    )
    for line in out.splitlines():
        if line.lower().startswith("mcp-session-id:"):
            return line.split(":", 1)[1].strip()
    return ""


def call(session: str, tool: str, args: dict) -> dict:
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    })
    out = host(
        f"curl -sS -X POST {HOST} "
        f"-H \"Content-Type: application/json\" "
        f"-H \"Accept: application/json, text/event-stream\" "
        f"-H \"Authorization: Bearer {BEARER}\" "
        f"-H \"mcp-session-id: {session}\" -d " + repr(payload)
    )
    if "data: " not in out:
        return {"_parse": "no_data", "_raw": out[:200]}
    data = out.split("data: ", 1)[1].split("\n", 1)[0]
    try:
        return json.loads(data)
    except Exception as e:
        return {"_parse": str(e), "_raw": data[:200]}


def text_of(j: dict) -> str:
    if "error" in j:
        return f"ERROR: {j['error']}"
    content = j.get("result", {}).get("content", [])
    if isinstance(content, list) and content:
        return content[0].get("text", "")
    return json.dumps(j)[:300]


def rows_of(text: str) -> int | None:
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


# ---------------------------------------------------------------------------
# Test catalogue
# ---------------------------------------------------------------------------

REGIONS = ["World", "Europe", "Asia", "Africa", "North America", "South America",
           "Oceania", "Eurasia", "Middle East"]
TECH_IDS_COST = ["solar_pv", "onshore_wind", "offshore_wind", "hydropower"]
TECH_ALIASES_PXWEB = ["Solar PV", "Solar", "Wind", "Hydropower", "Hydro",
                      "Onshore wind", "Offshore wind", "Solar thermal",
                      "Bioenergy", "Geothermal"]
COUNTRIES = ["AFG", "DEU", "CHN", "USA", "IND", "BRA", "FRA", "ESP", "NGA",
             "AUS", "ZAF", "MEX", "JPN", "KOR", "CAN", "GBR"]
YEARS = list(range(2010, 2026))
PXWEB_DATASETS = ["country_capacity", "country_generation", "region_capacity",
                  "region_generation", "re_share", "heat_generation",
                  "public_investments"]
ALL_DATASETS = PXWEB_DATASETS + ["lcoe_weighted"]


def random_pxweb_filters() -> dict:
    f = {}
    if random.random() < 0.8:
        f["technologies"] = random.sample(TECH_ALIASES_PXWEB,
                                          k=random.randint(1, 2))
    if random.random() < 0.7:
        f["countries"] = random.sample(COUNTRIES, k=random.randint(1, 2))
    if random.random() < 0.7:
        f["years"] = random.sample(YEARS, k=random.randint(1, 3))
    return f


def random_cost_filters() -> dict:
    f = {}
    if random.random() < 0.7:
        f["technologies"] = random.sample(TECH_IDS_COST, k=random.randint(1, 2))
    if random.random() < 0.7:
        f["regions"] = random.sample(REGIONS, k=random.randint(1, 2))
    if random.random() < 0.6:
        f["years"] = random.sample(YEARS, k=random.randint(1, 4))
    if random.random() < 0.3:
        f["countries"] = random.sample(COUNTRIES, k=random.randint(1, 2))
    return f


def gen_test(rng: random.Random) -> tuple[str, str, dict]:
    """Return (category, tool, args)."""
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
                 "filters": {"currencies": ["USD"],
                             "garbage": ["x"]},
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
                "",  # empty
                " ",  # whitespace
                "太阳能光伏发电成本",  # chinese
                "LCOE?" * 200,  # very long
                "!@#$%^&*()",  # punctuation only
                "renewable energy renewable energy renewable",  # repetition
                "what is the answer to life the universe and everything",
            ])})


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify(category: str, result: dict, text: str) -> tuple[str, str]:
    """Return (outcome, detail).

    Outcomes:
      ok                     - tool succeeded, rows returned
      ok-surface             - tool succeeded but server flagged filter/limit
                                coercion via filters_dropped/limit_clamped
      zero-rows              - tool succeeded, 0 rows (legit empty result)
      clean-error            - tool returned {"error":"..."} or {"isError":true} (correctly)
      validation-error       - pydantic rejected input
      unexpected-error       - 500-class server error
      server-error           - server-side exception
      malformed              - couldn't parse response
      transport-fail         - network error
      silent-coerce          - bad input silently coerced (server did NOT surface)
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

    # isError flag from FastMCP
    is_error = result.get("result", {}).get("isError", False)

    # Tool returned a JSON body with "error" key (correctly handled)
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

    # Surface-aware silent-coerce detection.
    # Server now exposes filters_applied / filters_dropped / limit_clamped
    # in the response body. Only flag silent-coerce if those fields are
    # missing AND the response otherwise looks like a coerced success.
    body_obj = None
    try:
        body_obj = json.loads(text)
    except Exception:
        body_obj = None

    if category == "query-edge-limits":
        if isinstance(body_obj, dict):
            if "limit_clamped" in body_obj or "limit_applied" in body_obj:
                return ("ok-surface",
                        f"limit_req={body_obj.get('limit_requested')}, "
                        f"applied={body_obj.get('limit_applied')}, "
                        f"clamped={body_obj.get('limit_clamped')}")
        return "silent-coerce", text[:80]

    if category == "query-weird-types":
        if isinstance(body_obj, dict):
            dropped = body_obj.get("filters_dropped")
            applied = body_obj.get("filters_applied")
            if dropped is not None or applied is not None:
                return ("ok-surface",
                        f"applied={applied}, dropped={dropped}")
        rc = rows_of(text)
        if rc == 0:
            return "silent-coerce", "zero rows for bad-typed input"

    rc = rows_of(text)
    if rc == 0:
        return "zero-rows", text[:80]
    if rc is not None and rc >= 1:
        return "ok", f"rows={rc}"
    return "ok", text[:80]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_batch(batch_id: int, n: int, users: int, seed: int):
    rng = random.Random(seed)
    sessions = [init_session(f"u{i}") for i in range(users)]
    sessions = [s for s in sessions if s]
    if not sessions:
        print("FATAL: no sessions")
        return

    outcomes = Counter()
    by_category = {}
    failures = []
    silent = []

    t0 = time.time()
    for i in range(n):
        cat, tool, args = gen_test(rng)
        sess = rng.choice(sessions)
        try:
            res = call(sess, tool, args)
            text = text_of(res)
        except Exception as e:
            outcomes["transport-fail"] += 1
            failures.append((cat, tool, str(e)[:120]))
            continue
        outcome, detail = classify(cat, res, text)
        outcomes[outcome] += 1
        by_category.setdefault(cat, Counter())[outcome] += 1
        if outcome in ("server-error", "malformed",
                       "transport-fail", "tool-error", "rpc-error"):
            failures.append((cat, tool, json.dumps(args)[:100], detail))
        if outcome == "silent-coerce":
            silent.append((cat, tool, json.dumps(args)[:120], detail))

    elapsed = time.time() - t0
    print(f"\n=== BATCH {batch_id} (n={n}, users={users}, seed={seed}, "
          f"{elapsed:.1f}s) ===")
    print("OUTCOMES:")
    for k, v in outcomes.most_common():
        print(f"  {k:20s} {v:5d}")
    print("BY CATEGORY:")
    for cat in sorted(by_category):
        oc = by_category[cat]
        line = "  ".join(f"{k}={v}" for k, v in oc.most_common())
        print(f"  {cat:25s} {line}")
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for cat, tool, args, det in failures[:15]:
            print(f"  [{cat}] {tool}({args}) :: {det}")
        if len(failures) > 15:
            print(f"  ... and {len(failures)-15} more")
    # Always dump every failure for offline analysis
    with open(f"/tmp/stress_batch_{batch_id}_failures.json", "w") as f:
        json.dump(failures, f, indent=2)
    with open(f"/tmp/stress_batch_{batch_id}_silent.json", "w") as f:
        json.dump(silent, f, indent=2)
    return outcomes, by_category, failures


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--batches", type=int, default=1)
    ap.add_argument("--per-batch", type=int, default=100)
    ap.add_argument("--users", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    all_outcomes = Counter()
    all_failures = []
    for b in range(args.batch, args.batch + args.batches):
        oc, _, fails = run_batch(b, args.per_batch, args.users,
                                 args.seed + b)
        all_outcomes.update(oc)
        all_failures.extend(fails)

    print(f"\n=== AGGREGATED ({args.batches} batches x {args.per_batch}) ===")
    for k, v in all_outcomes.most_common():
        print(f"  {k:20s} {v:5d}")
    if all_failures:
        print(f"\nTOTAL FAILURES: {len(all_failures)}")
        by_tool = Counter((cat, tool) for cat, tool, *_ in all_failures)
        for (cat, tool), n in by_tool.most_common(10):
            print(f"  {cat:20s} {tool:35s} {n}")
