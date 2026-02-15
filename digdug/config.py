"""Default configuration for DigDug."""


DEFAULTS = {
    # KoboldCpp connection
    "api_url": "http://localhost:5001",

    # Chunking parameters
    "chunk_size": 1500,        # tokens per chunk (well under Llama-3.1-8B's 128k context)
    "overlap_size": 200,       # tokens of sliding-window overlap between chunks

    # Generation parameters sent to KoboldCpp
    "max_length": 300,         # max tokens for LLM response
    "temperature": 0.1,        # low temp for deterministic analytical responses
    "top_p": 0.9,
    "rep_pen": 1.1,

    # Scanner behaviour
    "relevance_threshold": 0.6,  # minimum confidence to flag a chunk as relevant
    "deep_analysis_threshold": 0.8,  # confidence above which deep analysis is triggered
    "findings_log": "findings.log",
}
