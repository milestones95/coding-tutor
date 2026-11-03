"""Command-line entry points: `tutor` and `tutor-eval` (architecture §2, §8.2).

Only help exists for now; each task adds its own subcommand (`analyze`, `ask`, `migrate`,
`run`, `estimate`, …) when it is built. argparse keeps this dependency-free.
"""

import argparse
import sys


def _tutor_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tutor",
        description="LeetCode Tutor: analyze captured practice sessions and ask about your progress.",
    )
    p.add_subparsers(dest="command", metavar="<command>")
    return p


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


def main(argv: list[str] | None = None) -> int:
    return _run(_tutor_parser(), argv)


def eval_main(argv: list[str] | None = None) -> int:
    return _run(_eval_parser(), argv)


if __name__ == "__main__":
    sys.exit(main())
