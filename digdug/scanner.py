"""Progressive scanner — iterates chunks through the LLM for relevance."""

from __future__ import annotations

import json
import logging
import re

from digdug.chunker import Chunk, TextChunker
from digdug.client import KoboldCppClient
from digdug.config import DEFAULTS
from digdug.logger import Finding, FindingsLogger

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Prompt templates
# ------------------------------------------------------------------

TRIAGE_PROMPT = """\
<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a precise text-analysis assistant. Your ONLY job is to decide whether
the text below is relevant to the user's search query.

Respond with ONLY a JSON object (no other text):
{{"relevant": true/false, "confidence": 0.0-1.0, "summary": "one-sentence reason"}}
<|eot_id|><|start_header_id|>user<|end_header_id|>
SEARCH QUERY: {search_prompt}

CONTEXT FROM PREVIOUS SECTION:
{overlap}

TEXT TO EVALUATE:
{chunk_text}
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""

DEEP_ANALYSIS_PROMPT = """\
<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a thorough text-analysis assistant. The following text has been flagged
as highly relevant to the user's search query. Provide a detailed analysis.

Respond with ONLY a JSON object (no other text):
{{"analysis": "detailed multi-sentence analysis", "key_excerpt": "the most relevant passage from the text — include enough surrounding context to understand the finding (up to 1000 chars)"}}
<|eot_id|><|start_header_id|>user<|end_header_id|>
SEARCH QUERY: {search_prompt}

TEXT:
{chunk_text}
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""


# ------------------------------------------------------------------
# Scanner
# ------------------------------------------------------------------

class ProgressiveScanner:
    """Walk through chunked text, triage each chunk for relevance, and
    optionally perform deep analysis on high-confidence hits."""

    def __init__(
        self,
        client: KoboldCppClient,
        chunker: TextChunker | None = None,
        findings_logger: FindingsLogger | None = None,
        relevance_threshold: float | None = None,
        deep_analysis_threshold: float | None = None,
    ):
        self.client = client
        self.chunker = chunker or TextChunker()
        self.findings_logger = findings_logger or FindingsLogger()
        self.relevance_threshold = (
            relevance_threshold
            if relevance_threshold is not None
            else DEFAULTS["relevance_threshold"]
        )
        self.deep_analysis_threshold = (
            deep_analysis_threshold
            if deep_analysis_threshold is not None
            else DEFAULTS["deep_analysis_threshold"]
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def scan_text(self, text: str, search_prompt: str) -> FindingsLogger:
        """Scan raw text and return the populated findings logger."""
        chunks = self.chunker.chunk_text(text)
        return self._process_chunks(chunks, search_prompt)

    def scan_file(self, path: str, search_prompt: str) -> FindingsLogger:
        """Read a file, chunk it, and scan."""
        chunks = self.chunker.chunk_file(path)
        return self._process_chunks(chunks, search_prompt, source_path=path)

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _process_chunks(
        self,
        chunks: list[Chunk],
        search_prompt: str,
        source_path: str = "<text>",
    ) -> FindingsLogger:
        total = len(chunks)
        logger.info("Starting scan: %d chunks, query=%r", total, search_prompt)

        for chunk in chunks:
            logger.info("Processing chunk %d/%d …", chunk.index + 1, total)
            self._triage_chunk(chunk, search_prompt)

        # Write the human-readable summary at the end.
        if self.findings_logger.count:
            self.findings_logger.write_summary(search_prompt, source_path)

        logger.info(
            "Scan complete – %d findings (%d deep)",
            self.findings_logger.count,
            sum(1 for f in self.findings_logger.findings if f.deep),
        )
        return self.findings_logger

    def _triage_chunk(self, chunk: Chunk, search_prompt: str) -> None:
        """Ask the LLM whether *chunk* is relevant to the search prompt."""
        prompt = TRIAGE_PROMPT.format(
            search_prompt=search_prompt,
            overlap=chunk.overlap_prefix[-800:] if chunk.overlap_prefix else "(start of document)",
            chunk_text=chunk.text[:6000],  # safety cap
        )

        raw = self.client.generate(prompt)
        triage = self._parse_json(raw)

        if triage is None:
            logger.warning("Chunk %d: could not parse triage response, skipping", chunk.index)
            return

        relevant = triage.get("relevant", False)
        confidence = float(triage.get("confidence", 0.0))
        summary = triage.get("summary", "")

        logger.info(
            "Chunk %d: relevant=%s confidence=%.2f",
            chunk.index,
            relevant,
            confidence,
        )

        if not relevant or confidence < self.relevance_threshold:
            return

        # --- Build the finding -------------------------------------------
        analysis_text = ""
        is_deep = False

        if confidence >= self.deep_analysis_threshold:
            analysis_text, excerpt = self._deep_analyse(chunk, search_prompt)
            is_deep = True
        else:
            excerpt = chunk.text[:1000]

        finding = Finding(
            chunk_index=chunk.index,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            relevance_score=confidence,
            summary=summary,
            matched_excerpt=excerpt,
            analysis=analysis_text,
            deep=is_deep,
        )
        self.findings_logger.record(finding)

    def _deep_analyse(self, chunk: Chunk, search_prompt: str) -> tuple[str, str]:
        """Run a detailed analysis prompt and return (analysis, excerpt)."""
        prompt = DEEP_ANALYSIS_PROMPT.format(
            search_prompt=search_prompt,
            chunk_text=chunk.text[:6000],
        )
        raw = self.client.generate(prompt, max_length=800)
        parsed = self._parse_json(raw)

        if parsed is None:
            return ("(deep analysis response could not be parsed)", chunk.text[:1000])

        return (
            parsed.get("analysis", ""),
            parsed.get("key_excerpt", chunk.text[:1000]),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        """Best-effort extraction of a JSON object from LLM output."""
        # Try the raw text first.
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to find the first { … } block.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None
