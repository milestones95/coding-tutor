"""Command-line entry points: `tutor` and `tutor-eval` (architecture §2, §8.2).

Subcommands so far: `tutor prompts check` (T-005). Each task adds its own subcommand (`analyze`, `ask`, `migrate`,
`run`, `estimate`, …) when it is built. argparse keeps this dependency-free.
"""

import argparse
import sys
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
