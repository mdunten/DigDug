"""Command-line entry point for DigDug."""

from __future__ import annotations

import argparse
import logging
import sys

from digdug.chunker import TextChunker
from digdug.client import KoboldCppClient
from digdug.config import DEFAULTS
from digdug.logger import FindingsLogger
from digdug.scanner import ProgressiveScanner


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="digdug",
        description="Progressive text analysis powered by a local KoboldCpp / Llama instance.",
    )
    p.add_argument(
        "file",
        help="Path to the text file to analyse.",
    )
    p.add_argument(
        "prompt",
        help="Search prompt describing what to look for.",
    )
    p.add_argument(
        "--api-url",
        default=DEFAULTS["api_url"],
        help="KoboldCpp API base URL (default: %(default)s).",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULTS["chunk_size"],
        help="Tokens per chunk (default: %(default)s).",
    )
    p.add_argument(
        "--overlap",
        type=int,
        default=DEFAULTS["overlap_size"],
        help="Overlap tokens between chunks (default: %(default)s).",
    )
    p.add_argument(
        "--relevance-threshold",
        type=float,
        default=DEFAULTS["relevance_threshold"],
        help="Minimum confidence to record a finding (default: %(default)s).",
    )
    p.add_argument(
        "--deep-threshold",
        type=float,
        default=DEFAULTS["deep_analysis_threshold"],
        help="Confidence above which deep analysis runs (default: %(default)s).",
    )
    p.add_argument(
        "--log-file",
        default=DEFAULTS["findings_log"],
        help="Path for the JSON-lines findings log (default: %(default)s).",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # --- Connect to KoboldCpp ------------------------------------------
    client = KoboldCppClient(api_url=args.api_url)
    if not client.check_connection():
        print(
            f"ERROR: Cannot reach KoboldCpp at {args.api_url}. "
            "Make sure the server is running.",
            file=sys.stderr,
        )
        return 1

    # --- Set up components ---------------------------------------------
    chunker = TextChunker(
        chunk_size_tokens=args.chunk_size,
        overlap_tokens=args.overlap,
    )
    findings_logger = FindingsLogger(log_path=args.log_file)
    scanner = ProgressiveScanner(
        client=client,
        chunker=chunker,
        findings_logger=findings_logger,
        relevance_threshold=args.relevance_threshold,
        deep_analysis_threshold=args.deep_threshold,
    )

    # --- Run the scan --------------------------------------------------
    print(f"Scanning {args.file!r} for: {args.prompt!r}")
    print()

    fl = scanner.scan_file(args.file, args.prompt)

    # --- Report --------------------------------------------------------
    print()
    print(f"Done. {fl.count} finding(s) recorded to {args.log_file}")
    if fl.count:
        import os
        summary_name = os.path.splitext(args.log_file)[0] + ".summary.md"
        print(f"Summary: {summary_name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
