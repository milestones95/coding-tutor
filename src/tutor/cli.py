"""Command-line entry points: `tutor` and `tutor-eval` (architecture §2, §8.2).

Subcommands so far: `tutor prompts check` (T-005), `tutor smoke` (T-007), `tutor migrate` (T-008), `tutor analyze` / `rebuild-timelines` / `check` (T-011). Each task adds its own subcommand (`analyze`, `ask`, `migrate`,
`run`, `estimate`, …) when it is built. argparse keeps this dependency-free.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path


def _tutor_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tutor",
        description="LeetCode Tutor: analyze captured practice sessions and ask about your progress.",
    )
    sub = p.add_subparsers(dest="command", metavar="<command>")

    prompts = sub.add_parser("prompts", help="check versioned prompt files (architecture §7)")
    prompts_sub = prompts.add_subparsers(dest="prompts_command", metavar="<action>", required=True)
    check = prompts_sub.add_parser("check", help="fail if any prompt file doesn't match prompts/manifest.json")
    check.add_argument("--root", type=Path, default=None, help="prompts directory (default: the repo's prompts/)")
    check.set_defaults(handler=_prompts_check)

    smoke = sub.add_parser("smoke", help="M0 checkpoint: load one session, make one logged LLM call")
    smoke.add_argument("--session", required=True, help="session id in the frozen copy (paths.eval_capture_db)")
    smoke.add_argument("--model", default=None, metavar="PROVIDER:MODEL",
                       help="override the configured model for this run, e.g. openai:gpt-5.5")
    smoke.set_defaults(handler=_smoke)

    mig = sub.add_parser("migrate", help="apply pending analysis.db migrations (architecture §3.3)")
    mig.add_argument("--db", type=Path, default=None, help="database to migrate (default: paths.analysis_db)")
    mig.set_defaults(handler=_migrate)

    an = sub.add_parser("analyze", help="load captured sessions, write facts + condensed timelines to analysis.db")
    an.add_argument("--since", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD",
                    help="only sessions that started on or after this date (in time.timezone)")
    an.set_defaults(handler=_analyze)
    rb = sub.add_parser("rebuild-timelines", help="re-condense every analyzed session (after a condenser change)")
    rb.set_defaults(handler=_rebuild)
    ck = sub.add_parser("check", help="fail if any analysis row was built from a different condenser version")
    ck.set_defaults(handler=_check)
    return p


def _prompts_check(args: argparse.Namespace) -> int:
    from tutor.prompts import PROMPTS_ROOT, check_manifest

    root = args.root or PROMPTS_ROOT
    problems = check_manifest(root)
    for line in problems:
        print(f"FAIL {line}", file=sys.stderr)
    if problems:
        return 1
    print(f"ok: every prompt under {root} matches its manifest entry")
    return 0


def _smoke(args: argparse.Namespace) -> int:
    from tutor.capture.loader import CaptureFormatError
    from tutor.config import ConfigError, load_settings
    from tutor.llm import LLMError
    from tutor.prompts import PromptError
    from tutor.smoke import run_smoke

    try:
        ref, result = run_smoke(load_settings(), args.session, model=args.model)
    except LookupError as e:  # unknown or excluded session
        print(f"error: {e.args[0] if e.args else e}", file=sys.stderr)
        return 1
    except (LLMError, ConfigError, CaptureFormatError, PromptError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps({"session_id": args.session, "output": result.output.model_dump(), "call_id": result.call_id,
                      "model": str(ref), "cost_usd": result.usage.cost_usd}))
    return 0


def _migrate(args: argparse.Namespace) -> int:
    from tutor.config import ConfigError, load_settings
    from tutor.db.migrate import MigrationError, migrate

    try:
        settings = load_settings()
        target = args.db or settings.paths.analysis_db
        applied = migrate(target, settings=settings)
    except (MigrationError, ConfigError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"{target}: applied {applied}" if applied else f"{target}: up to date")
    return 0


def _pipeline_errors() -> tuple[type[BaseException], ...]:
    import sqlite3

    from tutor.analyzer.pipeline import PipelineError
    from tutor.capture.loader import CaptureFormatError, VerdictConflict
    from tutor.condense import CondenseBudgetError
    from tutor.config import ConfigError

    return (PipelineError, CaptureFormatError, VerdictConflict, CondenseBudgetError, ConfigError, sqlite3.Error)


def _analyze(args: argparse.Namespace) -> int:
    from tutor.analyzer.pipeline import analyze
    from tutor.config import load_settings
    from tutor.logs import new_run_id

    run_id = new_run_id()
    try:
        report = analyze(load_settings(), run_id=run_id, since=args.since)
    except _pipeline_errors() as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"analyze {run_id}: {report.stored} sessions stored")
    return 0


def _rebuild(args: argparse.Namespace) -> int:
    from tutor.analyzer.pipeline import rebuild_timelines
    from tutor.config import load_settings
    from tutor.logs import new_run_id

    run_id = new_run_id()
    try:
        r = rebuild_timelines(load_settings(), run_id=run_id)
    except _pipeline_errors() as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"rebuild-timelines {run_id}: {r.rebuilt} rebuilt, {len(r.orphaned)} orphaned (kept), "
          f"{r.not_analyzed} not analyzed yet (run `tutor analyze`)")
    return 0


def _check(args: argparse.Namespace) -> int:
    from tutor.analyzer.pipeline import check
    from tutor.config import load_settings

    try:
        stale = check(load_settings())
    except _pipeline_errors() as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for sid, analysis_v, timeline_v in stale:
        print(f"STALE {sid}: analysis built from {analysis_v}, timeline is {timeline_v or 'missing'}")
    if stale:
        return 1
    print("ok: every analysis row matches its timeline's condenser version")
    return 0


def _eval_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tutor-eval",
        description="Run evals: dataset → field or agent → graders → versioned result record.",
    )
    p.add_subparsers(dest="command", metavar="<command>")
    return p


def _run(parser: argparse.ArgumentParser, argv: list[str] | None) -> int:
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.handler(args)


def main(argv: list[str] | None = None) -> int:
    return _run(_tutor_parser(), argv)


def eval_main(argv: list[str] | None = None) -> int:
    return _run(_eval_parser(), argv)


if __name__ == "__main__":
    sys.exit(main())
