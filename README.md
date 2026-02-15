# DigDug

Progressive text analysis powered by a local KoboldCpp / Llama-3.1-8B instance.

DigDug scans large text files for content matching a user-provided search prompt.
It processes the text sequentially in chunks, maintains a sliding window of context
between chunks, and records findings to a local JSON-lines log file. Deep analysis
is triggered automatically for high-confidence matches.

## Requirements

- Python 3.10+
- A running [KoboldCpp](https://github.com/LostRuins/koboldcpp) instance with Llama-3.1-8B loaded

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Usage

```bash
# Basic scan
digdug path/to/document.txt "search for references to environmental policy changes"

# Custom thresholds and server URL
digdug data.txt "mentions of security vulnerabilities" \
    --api-url http://localhost:5001 \
    --chunk-size 2000 \
    --overlap 300 \
    --relevance-threshold 0.5 \
    --deep-threshold 0.75 \
    --log-file results.log \
    -v
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` | *(required)* | Path to the text file to analyse |
| `prompt` | *(required)* | Search prompt describing what to look for |
| `--api-url` | `http://localhost:5001` | KoboldCpp API base URL |
| `--chunk-size` | `1500` | Tokens per chunk |
| `--overlap` | `200` | Overlap tokens between chunks |
| `--relevance-threshold` | `0.6` | Minimum confidence to record a finding |
| `--deep-threshold` | `0.8` | Confidence above which deep analysis runs |
| `--log-file` | `findings.log` | Path for the JSON-lines findings log |
| `-v` / `--verbose` | off | Enable debug logging |

## Output

- **`findings.log`** — JSON-lines file with one record per finding
- **`findings.summary.md`** — Human-readable summary generated after the scan

## Architecture

```
digdug/
├── cli.py       # CLI entry point & argument parsing
├── client.py    # KoboldCpp REST API client with retry logic
├── chunker.py   # Text chunking with sliding-window overlap
├── config.py    # Default configuration values
├── logger.py    # Findings logger (JSON-lines + summary)
└── scanner.py   # Progressive scanning engine (triage + deep analysis)
```

### How it works

1. **Chunking** — The input text is split into overlapping chunks sized to fit
   within the LLM context window. Chunk boundaries snap to paragraph breaks
   when possible.

2. **Triage** — Each chunk is sent to the LLM with a lightweight prompt that
   asks: "Is this relevant?" The LLM returns a JSON verdict with a confidence
   score.

3. **Recording** — Chunks that meet the relevance threshold are recorded as
   findings in the log file immediately.

4. **Deep analysis** — Chunks above the deep-analysis threshold get a second,
   more detailed prompt. The LLM returns a multi-sentence analysis and
   identifies the most relevant excerpt.

5. **Summary** — After all chunks are processed, a Markdown summary is written.
