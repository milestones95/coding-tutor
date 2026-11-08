"""Run a judge on its calibration set and measure agreement with the human's grades (T-033; rule 8).
Tester-owned. Real LLM calls, through the one client (rule 5); prints the estimated cost first.

    uv run python evals/calibrate/calibrate_judge.py timeline [--version v1]

Reads evals/data/calibration/<judge>/v1.jsonl (dev cases only; the human's grades), runs the judge
on each summary with the case's dev session, and writes evals/results/calibration/<judge>-<ver>-<run>.json
with the judge's per-item answers and reasons. It never writes evals/calibration.json: the tester
records the number there after reading the result.
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))


def main(argv=None) -> int:
    from evals.calibrate.agreement import agreement, by_item
    from evals.graders.timeline_judge import ITEMS, TimelineJudge
    from tutor.condense import condense, render
    from tutor.config import load_settings
    from tutor.evals.cases import load_cases, load_case_session
    from tutor.llm import LLMClient
    from tutor.llm.pricing import DEFAULT_PRICING, price_for
    from tutor.logs import new_run_id

    ap = argparse.ArgumentParser()
    ap.add_argument("judge", choices=["timeline"])
    ap.add_argument("--version", default="v1")
    a = ap.parse_args(argv)

    rows = [json.loads(x) for x in (REPO / "evals/data/calibration/timeline/v1.jsonl").read_text().splitlines() if x.strip()]
    cases = {c.case_id: c for c in load_cases("timeline", "dev")}   # dev only: the loader refuses test anyway
    settings = load_settings()
    client = LLMClient(settings)
    judge = TimelineJudge()
    judge.version = a.version
    judge.run_id = new_run_id()
    ref = client.model_for(judge.field)
    print(f"estimate: {len(rows)} calls, ${len(rows) * price_for(DEFAULT_PRICING, str(ref)).cost(5000, 700):.2f}",
          file=sys.stderr)

    human, judged, out, cost = [], [], [], 0.0
    for r in rows:
        case = cases[r["case_id"]]
        timeline = render(condense(load_case_session(case, settings=settings)))
        o = judge.judge(case.expected, timeline, r["summary"], client=client)
        cost += judge.last_usage.cost_usd if judge.last_usage else 0.0
        human.append(r["human"])
        judged.append({i: getattr(o, i).met for i in ITEMS})
        out.append({"item_id": r["item_id"], "human": r["human"], "judge": o.model_dump()})
    res = {"judge": "timeline-judge", "version": a.version, "model": str(ref), "run_id": judge.run_id,
           **agreement(human, judged), "by_item": by_item(human, judged), "cost_usd": round(cost, 4), "items": out}
    dest = REPO / "evals/results/calibration" / f"timeline-judge-{a.version}-{judge.run_id}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    caught, misses = res["misses_caught"]
    print(f"timeline-judge-{a.version} @ {ref}: agreement {res['agreement']:.2f} (n={res['n']}), "
          f"always-yes would get {res['always_yes']:.2f}, misses caught {caught}/{misses}, "
          f"${res['cost_usd']:.2f} | {dest.relative_to(REPO)}")
    for i, (ag, n) in res["by_item"].items():
        print(f"  {i}: {ag}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
