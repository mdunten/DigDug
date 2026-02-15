"""Findings logger — writes structured records to a local log file."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from digdug.config import DEFAULTS

logger = logging.getLogger(__name__)


@dataclass
class Finding:
    """A single finding produced by the scanner."""

    chunk_index: int
    start_char: int
    end_char: int
    relevance_score: float
    summary: str
    matched_excerpt: str
    analysis: str = ""
    deep: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FindingsLogger:
    """Append-only JSON-lines logger that persists findings to disk."""

    def __init__(self, log_path: str | None = None):
        self.log_path = log_path or DEFAULTS["findings_log"]
        self.findings: list[Finding] = []

    def record(self, finding: Finding) -> None:
        """Persist a finding to the log file and keep it in memory."""
        self.findings.append(finding)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(finding), ensure_ascii=False) + "\n")
        logger.info(
            "Finding #%d recorded (chunk %d, relevance %.2f, deep=%s)",
            len(self.findings),
            finding.chunk_index,
            finding.relevance_score,
            finding.deep,
        )

    def write_summary(self, search_prompt: str, source_path: str) -> str:
        """Write a human-readable summary and return its path.

        The summary is placed next to the log file with a ``.summary.md``
        extension.
        """
        summary_path = os.path.splitext(self.log_path)[0] + ".summary.md"
        with open(summary_path, "w", encoding="utf-8") as fh:
            fh.write(f"# DigDug Analysis Summary\n\n")
            fh.write(f"**Source:** `{source_path}`\n\n")
            fh.write(f"**Search prompt:** {search_prompt}\n\n")
            fh.write(f"**Total findings:** {len(self.findings)}\n\n")
            fh.write(f"**Deep analyses:** {sum(1 for f in self.findings if f.deep)}\n\n")
            fh.write("---\n\n")

            for i, f in enumerate(self.findings, 1):
                fh.write(f"## Finding {i}\n\n")
                fh.write(f"- **Chunk:** {f.chunk_index}\n")
                fh.write(f"- **Character range:** {f.start_char}–{f.end_char}\n")
                fh.write(f"- **Relevance:** {f.relevance_score:.2f}\n")
                fh.write(f"- **Deep analysis:** {'Yes' if f.deep else 'No'}\n\n")
                fh.write(f"### Summary\n\n{f.summary}\n\n")
                if f.analysis:
                    fh.write(f"### Deep Analysis\n\n{f.analysis}\n\n")
                fh.write(f"### Excerpt\n\n```\n{f.matched_excerpt}\n```\n\n")
                fh.write("---\n\n")

        logger.info("Summary written to %s", summary_path)
        return summary_path

    @property
    def count(self) -> int:
        return len(self.findings)
