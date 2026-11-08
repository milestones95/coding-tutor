"""The eval runner: dataset → predictor → graders → versioned result record (architecture §8.2, §8.3; D-051).

One shape for every suite: load the cases (the sealed-split lock lives in `load_cases`), load each
case's `Session`, hand the predictor that `Session` and nothing else (labels stay here, §4.3 #1),
grade the output against the case, then aggregate overall, real-only and synthetic-only. Every
record names what produced it (rule 7), and a test-split run keeps aggregates only (rule 2).

A predictor is any callable `Session -> dict` with `.name` and `.version`: the keyword baseline
now, the LLM fields from M3.
"""

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from tutor.condense import CONDENSER_VERSION
from tutor.config import REPO_ROOT, Settings
from tutor.evals.cases import DEFAULT_ROOT, CaseError, load_case_session, load_cases
from tutor.llm import LLMClient, ModelRef
from tutor.llm.client import Usage
from tutor.llm.pricing import DEFAULT_PRICING, price_for
from tutor.logs import new_run_id


class Predictor(Protocol):
    name: str
    version: str

    def __call__(self, session: Any) -> dict: ...


def _evals_importable() -> None:
    """Graders and the baseline are tester-owned files under <repo>/evals/ (D-051)."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def graders_for(suite: str) -> list:
    _evals_importable()
    if suite == "algorithm":
        from evals.graders.algorithm_overlap import AlgorithmOverlap

        return [AlgorithmOverlap()]
    if suite == "failure":
        from evals.graders.failure_type_exact import FailureTypeExact

        return [FailureTypeExact()]
    if suite == "timeline":   # the calibrated judge; it counts sentences by code itself (D-062, D-064)
        from evals.graders.timeline_judge import TimelineJudge

        return [TimelineJudge()]
    raise NotImplementedError(f"no graders for suite {suite!r} yet (failure: M3, timeline: M4)")


class AlgorithmPredictor:
    """The algorithm field as a runner predictor (D-054): the same function the pipeline calls.

    The runner sets `run_id` before the first case so every logged call carries the record's id,
    and reads `last_usage` after each call for the per-case cost and tokens.
    """

    name = "algorithm"

    def __init__(self, settings: Settings, *, client: LLMClient | None = None, model: ModelRef | None = None):
        from tutor.fields.algorithm import PROMPT, prompt_for

        self._settings, self._model = settings, model
        self._client = client or LLMClient(settings)
        prompt = prompt_for(settings)
        self.version = prompt.version
        self.prompt_versions = {PROMPT: prompt.version}
        self.prompt_sha256 = {PROMPT: prompt.sha256}
        self.ref = self._client.model_for(PROMPT, model)
        self.provider = self.ref.provider
        self.run_id = new_run_id()
        self.last_usage: Usage | None = None

    @property
    def est_cost_per_call(self) -> float:
        # ~2,000 tokens in (prompt + a typical final solution), ~500 out (including reasoning tokens)
        return price_for(DEFAULT_PRICING, str(self.ref)).cost(2000, 500)

    def __call__(self, session: Any) -> dict:
        from tutor.fields.algorithm import algorithm

        self.last_usage = None
        result = algorithm(session, client=self._client, settings=self._settings, run_id=self.run_id,
                           model=self._model)
        self.last_usage = result.usage
        return {"labels": [a.value for a in result.output.algorithms]}


class FailurePredictor:
    """The failure field as a runner predictor (D-056). `last_usage` is None for a session that
    made no call (passed), so its row costs nothing."""

    name = "failure"

    def __init__(self, settings: Settings, *, client: LLMClient | None = None, model: ModelRef | None = None):
        from tutor.fields.failure import PROMPT, prompt_for

        self._settings, self._model = settings, model
        self._client = client or LLMClient(settings)
        prompt = prompt_for(settings)
        self.version = prompt.version
        self.prompt_versions = {PROMPT: prompt.version}
        self.prompt_sha256 = {PROMPT: prompt.sha256}
        self.ref = self._client.model_for(PROMPT, model)
        self.provider = self.ref.provider
        self.run_id = new_run_id()
        self.last_usage: Usage | None = None

    @property
    def est_cost_per_call(self) -> float:
        # ~3,000 tokens in (prompt + a condensed timeline), ~100 out; passed sessions make no call
        return price_for(DEFAULT_PRICING, str(self.ref)).cost(3000, 100)

    def __call__(self, session: Any) -> dict:
        from tutor.fields.failure import failure

        self.last_usage = None
        r = failure(session, client=self._client, settings=self._settings, run_id=self.run_id, model=self._model)
        self.last_usage = r.usage
        o = r.output
        return {"failure_type": o.failure_type.value, "source": o.source, "explanation": o.explanation}


class TimelinePredictor:
    """The timeline field as a runner predictor (D-060): the same function the pipeline calls."""

    name = "timeline"

    def __init__(self, settings: Settings, *, client: LLMClient | None = None, model: ModelRef | None = None):
        from tutor.fields.timeline import PROMPT, prompt_for

        self._settings, self._model = settings, model
        self._client = client or LLMClient(settings)
        prompt = prompt_for(settings)
        self.version = prompt.version
        self.prompt_versions = {PROMPT: prompt.version}
        self.prompt_sha256 = {PROMPT: prompt.sha256}
        self.ref = self._client.model_for(PROMPT, model)
        self.provider = self.ref.provider
        self.run_id = new_run_id()
        self.last_usage: Usage | None = None

    @property
    def est_cost_per_call(self) -> float:
        # ~3,000 tokens in (prompt + a condensed timeline), ~250 out (3–5 sentences)
        return price_for(DEFAULT_PRICING, str(self.ref)).cost(3000, 250)

    def __call__(self, session: Any) -> dict:
        from tutor.fields.timeline import timeline

        self.last_usage = None
        r = timeline(session, client=self._client, settings=self._settings, run_id=self.run_id, model=self._model)
        self.last_usage = r.usage
        return {"summary": r.output.summary}


class FailureRulesPredictor:
    """Failure type from the rules alone (`rules-v1`, D-055): it measures the rule-decided half of
    the failure suite before the LLM exists. A status no rule decides raises, so the runner scores
    that case as an error."""

    name, version = "failure_rules", "rules-v1"

    def __init__(self, settings: Settings):
        self._settings = settings
        self.run_id = new_run_id()

    def __call__(self, session: Any) -> dict:
        from tutor.fields.deterministic import status
        from tutor.fields.failure import failure_rule

        st = status(session, settings=self._settings, run_id=self.run_id).status
        ft = failure_rule(st)
        if ft is None:
            raise LookupError(f"no rule decides status {st.value!r}; the LLM field does (T-026)")
        return {"failure_type": ft.value, "source": "rule", "explanation": None}


def predictor_named(name: str, *, settings: Settings | None = None, client: LLMClient | None = None,
                    model: ModelRef | None = None) -> Predictor:
    _evals_importable()
    if name == "keyword_baseline":
        from evals.graders.keyword_baseline import KeywordBaseline

        return KeywordBaseline()
    if name == "algorithm":
        if settings is None:
            raise ValueError("the algorithm predictor needs settings")
        return AlgorithmPredictor(settings, client=client, model=model)
    if name == "failure":
        if settings is None:
            raise ValueError("the failure predictor needs settings")
        return FailurePredictor(settings, client=client, model=model)
    if name == "failure_rules":
        if settings is None:
            raise ValueError("the failure_rules predictor needs settings")
        return FailureRulesPredictor(settings)
    if name == "timeline":
        if settings is None:
            raise ValueError("the timeline predictor needs settings")
        return TimelinePredictor(settings, client=client, model=model)
    raise ValueError(f"unknown predictor {name!r}; available: keyword_baseline, algorithm, failure, failure_rules, "
                     "timeline")


def _git() -> tuple[str, bool]:
    def out(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()

    return out("rev-parse", "HEAD") or "unknown", bool(out("status", "--porcelain"))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def estimate(suite: str, split: str, *, predictor: Predictor, repeats: int = 1, root: Path | None = None,
             milestone: str | None = None) -> dict:
    """Projected calls and cost; makes no predictor calls. Non-LLM predictors cost nothing."""
    cases = load_cases(suite, split, root=root or DEFAULT_ROOT, milestone=milestone)
    per_call = float(getattr(predictor, "est_cost_per_call", 0.0))
    return {"cases": len(cases), "calls": len(cases) * repeats, "cost_usd": round(len(cases) * repeats * per_call, 6)}


CALIBRATED_AT = 0.85   # rule 8: a judge's numbers count only at this agreement with the human's grades


def _judge_info(judge: Any, client: LLMClient, root: Path) -> dict:
    """record["judge"] (§8.3): who judged, on which model, and whether that exact version is calibrated."""
    ref = client.model_for(judge.field)
    return {"name": judge.name, "version": judge.version, "provider": ref.provider, "model": ref.model,
            "calibrated": _is_calibrated(judge.name, judge.version, root / "calibration.json")}


def _is_calibrated(name: str, version: str, path: Path) -> bool:
    """True only when `path` lists this judge's exact version at agreement >= 0.85 (D-061). A missing
    or unreadable file means uncalibrated: the safe reading, since an uncalibrated number can't decide."""
    try:
        entries = json.loads(path.read_text()).get("entries", [])
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return False
    return any(isinstance(e, dict) and e.get("judge") == name and e.get("version") == version
               and isinstance(e.get("agreement"), (int, float)) and e["agreement"] >= CALIBRATED_AT
               for e in entries)


def _by_metric(rows: list[dict]) -> dict[str, dict]:
    """Mean and count per metric over rows that ran: a judge emits several checklist metrics, and
    `accuracy` reads only the first grade (D-061)."""
    values: dict[str, list[float]] = {}
    for r in rows:
        if r["error"]:
            continue
        for g in r["grades"]:
            values.setdefault(g["metric"], []).append(g["value"])
    return {m: {"mean": sum(v) / len(v), "n": len(v)} for m, v in values.items()}


def run(suite: str, split: str, *, predictor: Predictor, settings: Settings, repeats: int = 1,
        milestone: str | None = None, root: Path | None = None, results_dir: Path | None = None,
        graders: list | None = None, judge_client: LLMClient | None = None) -> dict:
    root = root or DEFAULT_ROOT
    cases = load_cases(suite, split, root=root, milestone=milestone)   # refuses a locked test split first
    _evals_importable()
    from evals.graders.base import GradeContext

    graders = graders if graders is not None else graders_for(suite)
    judges = [g for g in graders if getattr(g, "kind", None) == "llm_judge"]
    run_id, started = new_run_id(), _now()
    if hasattr(predictor, "run_id"):
        predictor.run_id = run_id      # the field's logged calls carry the record's run id
    if judges:
        judge_client = judge_client or LLMClient(settings)
        for j in judges:
            j.run_id = run_id          # judge calls are logged under the same run id
    rows: list[dict] = []
    for case in cases:
        session, load_error = None, None
        try:
            session = load_case_session(case, settings=settings, root=root)
        except CaseError as e:
            load_error = f"CaseError: {e}"
        for rep in range(1, repeats + 1):
            t0 = time.monotonic()
            output: dict = {}
            error = load_error
            if error is None:
                try:
                    output = predictor(session)
                except Exception as e:  # a failing predictor is a scored error, not a crashed run
                    error = f"{type(e).__name__}: {e}"
            usage = getattr(predictor, "last_usage", None) if error is None else None
            grades: list[dict] = []
            judge_cost = 0.0
            if error is None:
                # per case: judges that read the timeline need this case's Session (D-062)
                ctx = GradeContext(client=judge_client if judges else None, session=session)
                for gr in graders:
                    is_judge = gr in judges
                    try:
                        grades += [g.model_dump() for g in gr.grade(case, output, ctx)]
                    except Exception as e:   # a failing judge is a scored error, not a crashed run
                        error = f"judge: {type(e).__name__}: {e}" if is_judge else f"grader: {type(e).__name__}: {e}"
                        grades = []
                    finally:
                        ju = getattr(gr, "last_usage", None) if is_judge else None
                        judge_cost += ju.cost_usd if ju else 0.0
                    if error:
                        break
            rows.append({"case_id": case.case_id, "repeat": rep, "source": case.source,
                         "decider": "rule" if "rule_decided" in case.tags else "llm", "output": output,
                         "grades": grades, "error": error, "cost_usd": usage.cost_usd if usage else 0.0,
                         "judge_cost_usd": judge_cost,
                         "latency_ms": int((time.monotonic() - t0) * 1000),
                         "input_tokens": usage.input_tokens if usage else 0,
                         "output_tokens": usage.output_tokens if usage else 0})

    def accuracy(subset: list[dict]) -> float | None:
        if not subset:
            return None
        return sum((r["grades"][0]["value"] if r["grades"] else 0.0) for r in subset) / len(subset)

    by_case: dict[str, list[str]] = {}
    for r in rows:
        by_case.setdefault(r["case_id"], []).append(json.dumps(r["output"], sort_keys=True))
    consistency = (sum(len(set(v)) == 1 for v in by_case.values()) / len(by_case)) if by_case else None
    sha, dirty = _git()
    aggregates_extra: dict = {}
    if suite == "failure":   # §8.1: rule- and LLM-decided accuracy apart; the decider comes from the case (D-055)
        aggregates_extra["by_decider"] = {
            d: {"accuracy": accuracy([r for r in rows if r["decider"] == d]),
                "n": len({r["case_id"] for r in rows if r["decider"] == d})} for d in ("rule", "llm")}
    record = {
        "run_id": run_id, "suite": suite, "split": split,
        "dataset_version": cases[0].dataset_version if cases else f"{split}-v1",
        "started_at": started, "finished_at": _now(), "git_sha": sha, "git_dirty": dirty,
        "provider": getattr(predictor, "provider", "local"),
        "model": predictor.ref.model if hasattr(predictor, "ref") else f"{predictor.name}@{predictor.version}",
        "prompt_versions": dict(getattr(predictor, "prompt_versions", {})),
        "prompt_sha256": dict(getattr(predictor, "prompt_sha256", {})),
        "condenser_version": CONDENSER_VERSION,
        "judge": _judge_info(judges[0], judge_client, root) if judges and judge_client else None,
        "repeats": repeats,
        "metric": graders[0].name,
        "cases": [] if split == "test" else rows,      # rule 2: test runs keep aggregates only
        "aggregates": {
            "accuracy": accuracy(rows),
            "by_source": {src: {"accuracy": accuracy([r for r in rows if r["source"] == src]),
                                "n": len({r["case_id"] for r in rows if r["source"] == src})}
                          for src in ("real", "synthetic")},
            "consistency": consistency,
            "errors": sum(1 for r in rows if r["error"]),
            "by_metric": _by_metric(rows),
            **aggregates_extra,
        },
        "cost_usd_total": round(sum(r["cost_usd"] + r["judge_cost_usd"] for r in rows), 6),
    }
    out = (results_dir or root / "results")
    (out / suite).mkdir(parents=True, exist_ok=True)
    (out / suite / f"{run_id}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    with (out / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: v for k, v in record.items() if k != "cases"}, ensure_ascii=False) + "\n")
    return record


def _judge_label(judge: dict | None) -> str:
    if not judge:
        return "—"
    return f"{judge['name']}-{judge['version']}" + ("" if judge.get("calibrated") else " (uncalibrated)")


def summary_line(record: dict) -> str:
    def fmt(v: float | None) -> str:
        return "—" if v is None else f"{v:.2f}"

    a = record["aggregates"]
    parts = [f"{src} {fmt(a['by_source'][src]['accuracy'])} (n={a['by_source'][src]['n']})" for src in ("real", "synthetic")]
    if "by_decider" in a:
        parts += [f"{d} {fmt(a['by_decider'][d]['accuracy'])} (n={a['by_decider'][d]['n']})" for d in ("rule", "llm")]
    if record["prompt_versions"]:   # an LLM predictor: name the prompt and the model (rule 7)
        prompts = ", ".join(f"{n}-{v}" for n, v in record["prompt_versions"].items())
        made_by = f"prompt {prompts}, model {record['provider']}:{record['model']}"
    else:
        made_by = f"predictor {record['model']}"
    return (f"{record['suite']} {record['metric']} {fmt(a['accuracy'])} @ {made_by}, "
            f"dataset {record['dataset_version']}, condenser {record['condenser_version']}, "
            f"judge {_judge_label(record['judge'])} | {', '.join(parts)} | errors {a['errors']} | "
            f"consistency {fmt(a['consistency'])} | ${record['cost_usd_total']:.4f} | run {record['run_id']}")
