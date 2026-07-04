"""Command-line interface.

    stocktake build MODEL.py MAP.toml -o OUTDIR [--render]

Exit codes: 0 green build, 1 audit or schema failure, 2 usage error
(argparse). Failures are reported as-is; an adverse audit outcome is the
tool working, not the tool failing.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .build import build
from .errors import StocktakeError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="stocktake",
        description="Code-audited stock-and-flow diagrams in Forrester "
        "notation, built from hand-declared figures audited against "
        "numerical simulation code.",
    )
    parser.add_argument(
        "--version", action="version", version=f"stocktake {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser(
        "build", help="run the audited build for a model and concept map"
    )
    build_parser.add_argument("source", help="path to the model Python file")
    build_parser.add_argument("map", help="path to the concept map TOML")
    build_parser.add_argument(
        "-o", "--out", default=".", help="output directory (default: .)"
    )
    build_parser.add_argument(
        "--render",
        action="store_true",
        help="render each .dot to PDF and PNG if graphviz is installed",
    )

    args = parser.parse_args(argv)

    try:
        report = build(args.source, args.map, args.out, render=args.render)
    except StocktakeError as exc:
        print(f"stocktake: BUILD FAILED: {exc}", file=sys.stderr)
        return 1

    print(report.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
