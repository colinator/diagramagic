"""Command-line interface for diagramagic svg++ → SVG conversion."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Optional, Tuple

from .diagramagic import diagramagic


class ConversionError(Exception):
    pass


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert svg++ documents into pure SVG",
        epilog="Provide one or more input files, or use --text/STDIN to supply raw markup.",
    )
    parser.add_argument(
        "inputs",
        metavar="FILE",
        nargs="*",
        help="svg++ files to convert",
    )
    parser.add_argument(
        "--text",
        help="Raw svg++ markup to convert (mutually exclusive with STDIN input)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output path when converting a single input or --text",
    )
    parser.add_argument(
        "--out-dir",
        help="Directory for generated SVG files when converting multiple inputs",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Write the generated SVG to stdout instead of a file (single conversion only)",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def gather_sources(args: argparse.Namespace) -> list[Tuple[str, str]]:
    sources: list[Tuple[str, str]] = []

    if args.text is not None:
        sources.append(("text", args.text))

    for path_str in args.inputs:
        path = Path(path_str)
        if not path.exists():
            raise ConversionError(f"Input file not found: {path}")
        sources.append(("file", str(path)))

    if not sources:
        # Read from STDIN when no explicit text or files supplied.
        sources.append(("text", sys.stdin.read()))

    return sources


def convert_source(kind: str, payload: str) -> str:
    if kind == "file":
        text = Path(payload).read_text()
    else:
        text = payload
    return diagramagic(text)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    try:
        sources = gather_sources(args)
    except ConversionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    multiple = len(sources) > 1
    if args.stdout and multiple:
        print("error: --stdout is only valid for a single conversion", file=sys.stderr)
        return 2
    if args.output and multiple:
        print("error: --output cannot be used with multiple inputs", file=sys.stderr)
        return 2
    if args.output and args.stdout:
        print("error: --output and --stdout are mutually exclusive", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir).resolve() if args.out_dir else None
    if out_dir and not out_dir.exists():
        out_dir.mkdir(parents=True, exist_ok=True)

    for kind, payload in sources:
        svg_text = convert_source(kind, payload)

        if args.stdout:
            sys.stdout.write(svg_text)
            continue

        if args.output:
            Path(args.output).write_text(svg_text)
            continue

        if kind == "file":
            input_path = Path(payload)
            target_dir = out_dir or input_path.parent
            target_path = target_dir / (input_path.stem + ".svg")
            target_path.write_text(svg_text)
            print(f"Wrote {target_path}")
        else:
            # Text input with no target: print to stdout unless we already read from stdin with
            # nothing requested (avoid double newline).
            sys.stdout.write(svg_text)
            if not svg_text.endswith("\n"):
                sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
