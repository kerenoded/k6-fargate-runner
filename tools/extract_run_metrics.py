import argparse
import json
from pathlib import Path
from datetime import datetime, UTC


def _get_metric(data: dict, name: str):
    return data.get("metrics", {}).get(name, {})


def _values(metric: dict):
    return metric.get("values", {}) if metric else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("summary_json", help="Path to wrapped k6 summary.json")
    ap.add_argument("--out", default=None, help="Optional output JSON path (default: print to stdout)")
    args = ap.parse_args()

    p = Path(args.summary_json)
    raw = json.loads(p.read_text())

    # Support BOTH formats for backward compatibility
    if "k6" in raw:
        meta = raw
        data = raw["k6"]
        run_id = raw.get("run_id") or p.stem
        scenario_type = raw.get("scenario") or p.stem
        url = raw.get("target_url")
        method_type = raw.get("method_type")
    else:
        meta = {}
        data = raw
        run_id = p.stem
        scenario_type = p.stem
        url = None
        method_type = None
    # Prefer measure-only metrics (fallback if missing)
    dur = _values(_get_metric(data, "http_req_duration{scenario:measure}")) or _values(_get_metric(data, "http_req_duration"))
    req = _values(_get_metric(data, "http_reqs{scenario:measure}")) or _values(_get_metric(data, "http_reqs"))
    fail = _values(_get_metric(data, "http_req_failed{scenario:measure}")) or _values(_get_metric(data, "http_req_failed"))

    out = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "run_id": run_id,
        "url": url,
        "scenario": scenario_type,
        "method": method_type,
        "requests": req.get("count"),
        "rps": req.get("rate"),

        "error_rate": fail.get("rate"),

        "lat_avg_ms": dur.get("avg"),
        "lat_p90_ms": dur.get("p(90)"),
        "lat_p95_ms": dur.get("p(95)"),
        "lat_max_ms": dur.get("max"),
        "lat_min_ms": dur.get("min"),
        "lat_med_ms": dur.get("med"),
    }

    s = json.dumps(out)

    if args.out:
        Path(args.out).write_text(s + "\n")
        print(f"✅ Wrote {args.out}")
    else:
        print(s)


if __name__ == "__main__":
    main()