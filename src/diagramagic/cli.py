"""Command-line interface for diagramagic compile/render workflows."""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import traceback
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .diagramagic import FocusNotFoundError, diagramagic, render_png
from .resources import load_cheatsheet, load_patterns, load_prompt, load_skill


@dataclass
class CliError(Exception):
    code: str
    message: str
    hint: Optional[str] = None
    exit_code: int = 1
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    retryable: bool = True


class UsageError(Exception):
    pass


class FriendlyArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - argparse callback
        raise UsageError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = FriendlyArgumentParser(
        prog="diagramagic",
        description="Compile svg++ to SVG and render SVG/svg++ to PNG.",
    )
    parser.add_argument("--error-format", choices=["text", "json"], default="text")
    parser.add_argument("--debug", action="store_true")

    subparsers = parser.add_subparsers(dest="command")

    compile_parser = subparsers.add_parser("compile", help="Compile svg++ to SVG")
    compile_parser.add_argument("input", nargs="?", help="Input .svg++ file")
    compile_parser.add_argument("--text", help="Raw svg++ source")
    compile_parser.add_argument("--stdout", action="store_true", help="Write SVG to stdout")
    compile_parser.add_argument("-o", "--output", help="Output .svg path")
    compile_parser.add_argument(
        "--templates",
        nargs="+",
        metavar="GLOB",
        help="Template file globs (loaded left-to-right)",
    )

    render_parser = subparsers.add_parser("render", help="Render SVG/svg++ to PNG")
    render_parser.add_argument("input", nargs="?", help="Input .svg or .svg++ file")
    render_parser.add_argument("--text", help="Raw SVG/svg++ source")
    render_parser.add_argument("--stdout", action="store_true", help="Write PNG bytes to stdout")
    render_parser.add_argument("-o", "--output", help="Output .png path")
    render_parser.add_argument("--focus", help="Focus element id")
    render_parser.add_argument("--padding", type=float, default=20.0)
    render_parser.add_argument("--scale", type=float, default=1.0)
    render_parser.add_argument(
        "--templates",
        nargs="+",
        metavar="GLOB",
        help="Template file globs (loaded left-to-right)",
    )

    subparsers.add_parser("cheatsheet", help="Print svg++ quick reference")
    subparsers.add_parser("patterns", help="Print canonical svg++ pattern reference")
    subparsers.add_parser("prompt", help="Print short prompt fragment for agents")
    subparsers.add_parser("skill", help="Print integration skill instructions for agents")

    return parser


def _is_svgpp(text: str) -> bool:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return False
    local = root.tag.split("}", 1)[1] if root.tag.startswith("{") else root.tag
    return local == "diagram"


def _read_input(path: Optional[str], text: Optional[str]) -> tuple[str, str, Optional[Path]]:
    if path and text is not None:
        raise CliError(
            "E_ARGS",
            "--text cannot be combined with file input",
            hint="Use either FILE or --text.",
            exit_code=2,
        )

    if text is not None:
        return text, "<text>", None

    if path:
        input_path = Path(path)
        if not input_path.exists():
            raise CliError(
                "E_IO_READ",
                f"input file not found: {input_path}",
                exit_code=2,
                file=str(input_path),
            )
        try:
            return input_path.read_text(), str(input_path), input_path
        except OSError as exc:
            raise CliError(
                "E_IO_READ",
                f"failed to read input file: {input_path}",
                hint=str(exc),
                exit_code=2,
                file=str(input_path),
            )

    if sys.stdin.isatty():
        raise CliError(
            "E_ARGS",
            "no input provided",
            hint="Use a subcommand with FILE, --text, or pipe stdin.",
            exit_code=2,
        )

    data = sys.stdin.read()
    if not data.strip():
        raise CliError(
            "E_ARGS",
            "stdin was empty",
            hint="Pipe SVG/svg++ content into stdin.",
            exit_code=2,
        )
    return data, "<stdin>", None


def _resolve_template_sources(patterns: Optional[list[str]]) -> list[str]:
    if not patterns:
        return []

    paths: list[Path] = []
    for pattern in patterns:
        matches = [Path(match) for match in glob.glob(pattern)]
        if not matches:
            raise CliError(
                "E_TEMPLATE",
                f"template glob matched no files: {pattern}",
                hint="Provide at least one existing .svg++ template file.",
                exit_code=3,
            )
        paths.extend(sorted(matches))

    sources: list[str] = []
    for path in paths:
        try:
            sources.append(path.read_text())
        except OSError as exc:
            raise CliError(
                "E_TEMPLATE",
                f"failed to read template file: {path}",
                hint=str(exc),
                exit_code=3,
                file=str(path),
            )
    return sources


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content)
    except OSError as exc:
        raise CliError(
            "E_IO_WRITE",
            f"failed to write output file: {path}",
            hint=str(exc),
            exit_code=4,
            file=str(path),
        )


def _write_bytes(path: Path, content: bytes) -> None:
    try:
        path.write_bytes(content)
    except OSError as exc:
        raise CliError(
            "E_IO_WRITE",
            f"failed to write output file: {path}",
            hint=str(exc),
            exit_code=4,
            file=str(path),
        )


def _error_from_exception(exc: Exception) -> CliError:
    if isinstance(exc, CliError):
        return exc
    if isinstance(exc, FocusNotFoundError):
        return CliError(
            "E_FOCUS_NOT_FOUND",
            str(exc),
            hint="Check id attributes in your SVG/svg++ and retry --focus.",
            exit_code=4,
            retryable=True,
        )
    if isinstance(exc, ET.ParseError):
        line, column = getattr(exc, "position", (None, None))
        return CliError(
            "E_PARSE_XML",
            f"failed to parse XML: {exc}",
            hint="Ensure input is well-formed XML and escape &, <, > in text.",
            exit_code=2,
            line=line,
            column=column,
            retryable=True,
        )
    if isinstance(exc, ValueError):
        msg = str(exc)
        if "parse" in msg.lower() or "xml" in msg.lower():
            return CliError(
                "E_PARSE_XML",
                msg,
                hint="Ensure input is well-formed XML/svg++.",
                exit_code=2,
                retryable=True,
            )
        return CliError(
            "E_SVGPP_SEMANTIC",
            msg,
            hint="Check svg++ semantics and template usage.",
            exit_code=3,
            retryable=True,
        )
    return CliError(
        "E_INTERNAL",
        str(exc) or exc.__class__.__name__,
        hint="Re-run with --debug to see traceback.",
        exit_code=1,
        retryable=False,
    )


def _emit_error(err: CliError, *, error_format: str) -> None:
    if error_format == "json":
        payload = {
            "ok": False,
            "code": err.code,
            "message": err.message,
            "file": err.file,
            "line": err.line,
            "column": err.column,
            "hint": err.hint,
            "retryable": err.retryable,
        }
        sys.stderr.write(json.dumps(payload) + "\n")
        return

    sys.stderr.write(f"error[{err.code}]: {err.message}\n")
    if err.hint:
        sys.stderr.write(f"hint: {err.hint}\n")


def _handle_compile(args: argparse.Namespace) -> int:
    if args.stdout and args.output:
        raise CliError(
            "E_ARGS",
            "--stdout and --output are mutually exclusive",
            hint="Choose either --stdout or --output.",
            exit_code=2,
        )

    source, source_name, source_path = _read_input(args.input, args.text)
    template_sources = _resolve_template_sources(args.templates)
    svg_text = diagramagic(source, shared_template_sources=template_sources)

    if args.stdout or source_path is None:
        sys.stdout.write(svg_text)
        if not svg_text.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    output_path = Path(args.output) if args.output else source_path.with_suffix(".svg")
    _write_text(output_path, svg_text)
    print(f"Wrote {output_path}")
    return 0


def _handle_render(args: argparse.Namespace) -> int:
    if args.stdout and args.output:
        raise CliError(
            "E_ARGS",
            "--stdout and --output are mutually exclusive",
            hint="Choose either --stdout or --output.",
            exit_code=2,
        )
    if args.scale <= 0:
        raise CliError(
            "E_ARGS",
            "--scale must be > 0",
            hint="Use a positive scale factor like 1 or 2.",
            exit_code=2,
        )

    source, _source_name, source_path = _read_input(args.input, args.text)
    template_sources = _resolve_template_sources(args.templates)

    if _is_svgpp(source):
        svg_text = diagramagic(source, shared_template_sources=template_sources)
    else:
        if template_sources:
            raise CliError(
                "E_TEMPLATE",
                "--templates can only be used with svg++ input",
                hint="Remove --templates or provide <diag:diagram> input.",
                exit_code=3,
            )
        svg_text = source

    png_bytes = render_png(
        svg_text,
        scale=args.scale,
        focus_id=args.focus,
        padding=args.padding,
    )

    if args.stdout or source_path is None:
        sys.stdout.buffer.write(png_bytes)
        return 0

    output_path = Path(args.output) if args.output else source_path.with_suffix(".png")
    _write_bytes(output_path, png_bytes)
    print(f"Wrote {output_path}")
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = _build_parser()

    if not raw_argv:
        err = CliError(
            "E_ARGS",
            "missing subcommand",
            hint="Use one of: compile, render, cheatsheet, patterns, prompt, skill.",
            exit_code=2,
        )
        _emit_error(err, error_format="text")
        return err.exit_code

    debug_enabled = "--debug" in raw_argv or os.getenv("DIAGRAMAGIC_DEBUG") == "1"
    error_format = "text"
    if "--error-format" in raw_argv:
        idx = raw_argv.index("--error-format")
        if idx + 1 < len(raw_argv):
            error_format = raw_argv[idx + 1]

    try:
        args = parser.parse_args(raw_argv)
        error_format = args.error_format

        if args.command == "compile":
            return _handle_compile(args)
        if args.command == "render":
            return _handle_render(args)
        if args.command == "cheatsheet":
            print(load_cheatsheet())
            return 0
        if args.command == "patterns":
            print(load_patterns())
            return 0
        if args.command == "prompt":
            print(load_prompt())
            return 0
        if args.command == "skill":
            print(load_skill())
            return 0

        raise CliError(
            "E_ARGS",
            "missing subcommand",
            hint="Use one of: compile, render, cheatsheet, patterns, prompt, skill.",
            exit_code=2,
        )
    except UsageError as exc:
        err = CliError(
            "E_ARGS",
            str(exc),
            hint="Use subcommands: compile, render, cheatsheet, patterns, prompt, skill.",
            exit_code=2,
        )
        _emit_error(err, error_format=error_format)
        return err.exit_code
    except Exception as exc:  # pragma: no cover - exercised in integration tests
        err = _error_from_exception(exc)
        _emit_error(err, error_format=error_format)
        if debug_enabled:
            traceback.print_exc(file=sys.stderr)
        return err.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
