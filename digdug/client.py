"""KoboldCpp API client for local Llama-3.1-8B inference."""

import json
import logging
import time

import requests

from digdug.config import DEFAULTS

logger = logging.getLogger(__name__)


class KoboldCppClient:
    """Thin wrapper around the KoboldCpp REST API."""

    def __init__(self, api_url: str | None = None):
        self.api_url = (api_url or DEFAULTS["api_url"]).rstrip("/")
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def check_connection(self) -> bool:
        """Return True if the KoboldCpp server is reachable."""
        try:
            resp = self.session.get(f"{self.api_url}/api/v1/model", timeout=5)
            resp.raise_for_status()
            model_info = resp.json()
            logger.info("Connected to KoboldCpp – model: %s", model_info.get("result"))
            return True
        except requests.RequestException as exc:
            logger.error("Cannot reach KoboldCpp at %s: %s", self.api_url, exc)
            return False

    def generate(
        self,
        prompt: str,
        max_length: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        rep_pen: float | None = None,
    ) -> str:
        """Send a generation request and return the resulting text.

        Retries up to 3 times on transient network errors with exponential
        back-off (1 s, 2 s, 4 s).
        """
        payload = {
            "prompt": prompt,
            "max_length": max_length or DEFAULTS["max_length"],
            "temperature": temperature if temperature is not None else DEFAULTS["temperature"],
            "top_p": top_p if top_p is not None else DEFAULTS["top_p"],
            "rep_pen": rep_pen if rep_pen is not None else DEFAULTS["rep_pen"],
        }

        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                resp = self.session.post(
                    f"{self.api_url}/api/v1/generate",
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if results:
                    return results[0].get("text", "").strip()
                return ""
            except requests.RequestException as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning(
                    "KoboldCpp request failed (attempt %d/4): %s – retrying in %ds",
                    attempt + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)

        raise ConnectionError(
            f"KoboldCpp request failed after 4 attempts: {last_exc}"
        ) from last_exc

    def get_token_count(self, text: str) -> int:
        """Use the KoboldCpp token-count endpoint to count tokens.

        Falls back to a rough word-based estimate if the endpoint is
        unavailable.
        """
        try:
            resp = self.session.post(
                f"{self.api_url}/api/extra/tokencount",
                json={"prompt": text},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("value", self._estimate_tokens(text))
        except requests.RequestException:
            return self._estimate_tokens(text)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 chars per token for English text."""
        return max(1, len(text) // 4)
