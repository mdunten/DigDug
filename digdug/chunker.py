"""Text chunking with sliding-window context preservation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from digdug.config import DEFAULTS

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A single chunk of source text with positional metadata."""

    index: int
    text: str
    start_char: int
    end_char: int
    overlap_prefix: str  # context carried from the previous chunk


class TextChunker:
    """Split a large text into overlapping chunks sized by character count.

    KoboldCpp's ``/api/extra/tokencount`` can be used externally for precise
    token sizing, but for chunking purposes a character-based heuristic
    (≈4 chars/token) keeps things simple and avoids per-chunk API calls.
    """

    CHARS_PER_TOKEN = 4  # conservative estimate for English

    def __init__(
        self,
        chunk_size_tokens: int | None = None,
        overlap_tokens: int | None = None,
    ):
        self.chunk_tokens = chunk_size_tokens or DEFAULTS["chunk_size"]
        self.overlap_tokens = overlap_tokens or DEFAULTS["overlap_size"]

        self.chunk_chars = self.chunk_tokens * self.CHARS_PER_TOKEN
        self.overlap_chars = self.overlap_tokens * self.CHARS_PER_TOKEN

    def chunk_text(self, text: str) -> list[Chunk]:
        """Return an ordered list of overlapping :class:`Chunk` objects.

        The chunker tries to split on paragraph boundaries (double newlines)
        when possible so that logical sections aren't cut mid-sentence.
        """
        if not text:
            return []

        chunks: list[Chunk] = []
        pos = 0
        idx = 0

        while pos < len(text):
            end = min(pos + self.chunk_chars, len(text))

            # Try to snap the end to a paragraph boundary.
            if end < len(text):
                boundary = text.rfind("\n\n", pos + self.chunk_chars // 2, end)
                if boundary != -1:
                    end = boundary + 2  # include the double newline

            chunk_text = text[pos:end]

            # Build overlap prefix from the *previous* chunk.
            if pos == 0:
                overlap_prefix = ""
            else:
                overlap_start = max(0, pos - self.overlap_chars)
                overlap_prefix = text[overlap_start:pos]

            chunks.append(
                Chunk(
                    index=idx,
                    text=chunk_text,
                    start_char=pos,
                    end_char=end,
                    overlap_prefix=overlap_prefix,
                )
            )

            pos = end
            idx += 1

        logger.info(
            "Chunked %d chars into %d chunks (target %d tokens/chunk, %d overlap)",
            len(text),
            len(chunks),
            self.chunk_tokens,
            self.overlap_tokens,
        )
        return chunks

    def chunk_file(self, path: str, encoding: str = "utf-8") -> list[Chunk]:
        """Read a file and return its chunks."""
        with open(path, encoding=encoding) as fh:
            text = fh.read()
        return self.chunk_text(text)
