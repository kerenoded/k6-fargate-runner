#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta


def parse_ts(s: str) -> datetime:
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def load_runs(path: Path) -> list[dict]:
    rows: list[dict] = []
    for i, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"Invalid JSON on line {i} in {path}: {e}\nLINE: {line[:250]}")
    return rows


def pick_series(row: dict, metric: str) -> float | None:
    match metric:
        case "avg":
            return row.get("lat_avg_ms")
        case "p90":
            return row.get("lat_p90_ms")
        case "p95":
            return row.get("lat_p95_ms")
        case "rps":
            return row.get("rps")
        case "err":
            v = row.get("error_rate")
            return None if v is None else float(v) * 100.0
        case _:
            raise SystemExit(f"Unknown metric '{metric}'. Use: avg, p90, p95, rps, err")


def metric_title(metric: str) -> str:
    return {
        "avg": "avg latency (ms)",
        "rps": "Throughput (req/s)",
        "p90": "p90 latency (ms)",
        "p95": "p95 latency (ms)",
        "err": "Error rate (%)",
    }[metric]


def metric_ylabel(metric: str) -> str:
    return {
        "avg": "ms",
        "p90": "ms",
        "p95": "ms",
        "rps": "req/s",
        "err": "%",
    }[metric]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="test-results/runs.jsonl", help="Path to JSONL ledger of extracted runs")
    ap.add_argument("--url", default=None, help="Filter by URL (exact match)")
    ap.add_argument("--metrics", default="avg,rps,p90,p95,err", help="Comma-separated: avg,rps,p90,p95,err")
    ap.add_argument("--group-by", default="none", choices=["none", "url", "scenario"])
    ap.add_argument("--show", action="store_true", help="Show interactive window (default unless --save only).")
    ap.add_argument("--save", default=None, help="Save to file (single image), e.g. out.png")
    args = ap.parse_args()

    layout_metrics = ["avg", "rps", "p90", "p95", "err"]
    metrics_requested = [m.strip() for m in args.metrics.split(",") if m.strip()]
    allowed = set(layout_metrics)
    bad = [m for m in metrics_requested if m not in allowed]
    if bad:
        raise SystemExit(f"Unknown metrics: {bad}. Allowed: {sorted(allowed)}")
    enabled = set(metrics_requested) if metrics_requested else allowed

    runs_path = Path(args.runs)
    if not runs_path.exists():
        raise SystemExit(
            f"Missing {runs_path}.\n"
            f"Create it by appending JSONL rows, e.g:\n"
            f"  mkdir -p test-results\n"
            f"  python tools/extract_run_metrics.py <summary.json> >> {runs_path}\n"
        )

    rows = load_runs(runs_path)
    if args.url:
        rows = [r for r in rows if r.get("url") == args.url]
    if not rows:
        raise SystemExit("No runs to plot (file empty or filtered everything out).")

    rows.sort(key=lambda r: parse_ts(r["ts"]))

    def group_key(r: dict) -> str:
        if args.group_by == "none":
            return "all"
        if args.group_by == "url":
            return r.get("url", "unknown_url")
        if args.group_by == "scenario":
            return r.get("scenario", "unknown_scenario")
        return "all"

    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(group_key(r), []).append(r)

    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    # Always show day/month (and time) so you don't lose context across days.
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    fmt = mdates.DateFormatter("%d/%m %H:%M")

    # Layout:
    # [avg] [rps]
    # [p90] [p95]
    # [ err spans both columns ]
    fig = plt.figure(figsize=(14, 8), constrained_layout=True)
    fig.get_layout_engine().set(w_pad=0.15, h_pad=0.15, hspace=0.05, wspace=0.05)
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1.1], hspace=0.05, wspace=0.05)

    ax_avg = fig.add_subplot(gs[0, 0])
    ax_rps = fig.add_subplot(gs[0, 1], sharex=ax_avg)
    ax_p90 = fig.add_subplot(gs[1, 0], sharex=ax_avg)
    ax_p95 = fig.add_subplot(gs[1, 1], sharex=ax_avg)
    ax_err = fig.add_subplot(gs[2, :], sharex=ax_avg)

    axes_by_metric = {
        "avg": ax_avg,
        "rps": ax_rps,
        "p90": ax_p90,
        "p95": ax_p95,
        "err": ax_err,
    }

    total_points = 0

    def plot_metric(metric: str):
        nonlocal total_points
        ax = axes_by_metric[metric]

        if metric not in enabled:
            ax.set_axis_off()
            return

        # Build series per group for THIS metric
        series: dict[str, tuple[list[datetime], list[float]]] = {}
        for g, items in groups.items():
            x: list[datetime] = []
            y: list[float] = []
            for r in items:
                val = pick_series(r, metric)
                if val is None:
                    continue
                x.append(parse_ts(r["ts"]))
                y.append(float(val))
            if x:
                series[g] = (x, y)

        ax.set_title(metric_title(metric))
        ax.set_ylabel(metric_ylabel(metric))

        # Apply date axis formatting (shared)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(fmt)

        if not series:
            ax.text(0.5, 0.5, "no datapoints", ha="center", va="center", transform=ax.transAxes)
            return

        for g, (x, y) in series.items():
            label = None if args.group_by == "none" else g
            ax.plot(x, y, marker="o", label=label)
            total_points += len(x)

        # If only a single timestamp exists, widen x-limits so it doesn't look empty
        all_x = [t for (x, _) in series.values() for t in x]
        if len(set(all_x)) == 1:
            t = all_x[0]
            ax.set_xlim(t - timedelta(minutes=5), t + timedelta(minutes=5))

        if args.group_by != "none":
            ax.legend(fontsize=8)

    for m in layout_metrics:
        plot_metric(m)

    # Make x-tick labels visible on all axes and rotate them
    # (sharex hides them by default, and we need to do this manually instead of autofmt_xdate)
    for ax in [ax_avg, ax_rps, ax_p90, ax_p95, ax_err]:
        ax.tick_params(axis='x', which='both', labelbottom=True, labelsize=8)
        ax.set_xlabel("time", fontsize=9)
        for label in ax.get_xticklabels():
            label.set_rotation(25)
            label.set_ha('right')

    print(
        f"Loaded {len(rows)} runs from {runs_path}; "
        f"plotted {total_points} points across up to 5 panels."
    )

    if args.save:
        plt.savefig(args.save, dpi=150)
        print(f"✅ Saved: {args.save}")

    if args.show or not args.save:
        plt.show()


if __name__ == "__main__":
    main()