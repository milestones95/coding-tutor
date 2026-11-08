"""Noise band from a repeated run (T-035; /test "use the noise band"). Tester-owned, deterministic.

A record made with `repeats=N` holds N rows per case. For one metric, each repeat gets its own mean
over the rows that have that metric; the band is the spread (max - min) of those N means. A later
change inside the band is noise; outside it is a regression.

    uv run python evals/report/repeat_band.py evals/results/<suite>/<run_id>.json [metric ...]
"""

import json
import sys
from pathlib import Path


def per_repeat(record: dict, metric: str) -> list[float]:
    """The metric's mean in each repeat, repeat 1 first. Rows without the metric don't count."""
    sums: dict[int, list[float]] = {}
    for r in record["cases"]:
        for g in r["grades"]:
            if g["metric"] == metric:
                sums.setdefault(r["repeat"], []).append(g["value"])
    return [sum(v) / len(v) for _, v in sorted(sums.items())]


def accuracy_per_repeat(record: dict) -> list[float]:
    """The runner's accuracy (first grade; a row with no grades counts 0) in each repeat."""
    by: dict[int, list[float]] = {}
    for r in record["cases"]:
        by.setdefault(r["repeat"], []).append(r["grades"][0]["value"] if r["grades"] else 0.0)
    return [sum(v) / len(v) for _, v in sorted(by.items())]


def band(values: list[float]) -> dict:
    if not values:
        raise ValueError("no values")
    return {"values": [round(v, 4) for v in values], "mean": round(sum(values) / len(values), 4),
            "min": round(min(values), 4), "max": round(max(values), 4), "band": round(max(values) - min(values), 4)}


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    rec = json.loads(Path(argv[0]).read_text())
    metrics = argv[1:] or sorted({g["metric"] for r in rec["cases"] for g in r["grades"]})
    print(f"{rec['suite']} run {rec['run_id']} · repeats {rec['repeats']} · dataset {rec['dataset_version']} · "
          f"prompt {rec['prompt_versions']} · judge {rec['judge']}")
    print(f"  accuracy: {band(accuracy_per_repeat(rec))}")
    for m in metrics:
        print(f"  {m}: {band(per_repeat(rec, m))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
