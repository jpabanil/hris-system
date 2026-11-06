"""`python -m seeds run --fresh` drops the configured database and loads the demo company."""

from __future__ import annotations

import argparse
import asyncio
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m seeds")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Load the demo company")
    run.add_argument("--fresh", action="store_true", help="Drop the database before loading")
    args = parser.parse_args(argv)
    if args.command == "run":
        from seeds.runner import run as seed_run

        asyncio.run(seed_run(fresh=args.fresh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
