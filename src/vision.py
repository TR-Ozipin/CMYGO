"""Vision LLM client for shinagaki image recognition.

Uses OpenAI-compatible API (works with LM Studio, GPT-4o, Qwen-VL, etc.)
to extract structured information from shinagaki (品書) images.
"""

import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default prompt template for shinagaki parsing
SHINAGAKI_PROMPT = """\
You are a shinagaki (品書) parser. Extract structured information from this \
Comike doujinshi menu image.

Return JSON only:
{
  "booth": "booth location (e.g., 水 西あ52ab)",
  "circle_name": "circle/doujin group name",
  "author": "author/illustrator name",
  "event": "event name (e.g., ComiC107)",
  "twitter_id": "twitter handle without @ (if visible)",
  "confidence": 0.0,
  "raw_text": "all recognized text in reading order"
}

Rules:
- Booth is usually at the top, largest text
- Circle name is the most prominent text (often with logo)
- Ignore menu item listings and small print
- If a field is not visible, return null
- Preserve original Japanese/Chinese characters, do not translate
- Set confidence between 0.0 and 1.0 based on how sure you are about the \
  overall extraction quality
"""


def compute_image_hash(image_path: Path) -> str:
    """Compute SHA-256 hash of an image file for caching."""
    h = hashlib.sha256()
    with open(image_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def encode_image_base64(image_path: Path) -> str:
    """Read and encode an image file as base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _guess_mime_type(image_path: Path) -> str:
    """Guess MIME type from file extension."""
    suffix = image_path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mime_map.get(suffix, "image/jpeg")


class VisionClient:
    """Client for Vision LLM recognition via OpenAI-compatible API.

    Works with:
    - LM Studio (local, default: http://localhost:1234/v1)
    - OpenAI GPT-4o
    - Qwen-VL (via DashScope compatible endpoint)
    - Any OpenAI-compatible vision API

    Args:
        api_base: Base URL of the API (e.g., "http://localhost:1234/v1").
        api_key: API key (LM Studio accepts any value, e.g., "lm-studio").
        model: Model name to use.
        confidence_threshold: Minimum confidence to accept a result.
    """

    def __init__(
        self,
        api_base: str = "http://localhost:1234/v1",
        api_key: str = "lm-studio",
        model: str = "qwen2.5-vl-7b",
        confidence_threshold: float = 0.8,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.confidence_threshold = confidence_threshold

    def recognize(self, image_path: Path) -> dict[str, Any]:
        """Recognize shinagaki content from an image file.

        Args:
            image_path: Path to the shinagaki image.

        Returns:
            Parsed result dict with keys: booth, circle_name, author,
            event, twitter_id, confidence, raw_text.
            Returns empty dict on failure.
        """
        import urllib.request
        import urllib.error

        image_b64 = encode_image_base64(image_path)
        mime_type = _guess_mime_type(image_path)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SHINAGAKI_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_b64}",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.1,
        }

        url = f"{self.api_base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        logger.debug("Calling Vision API: %s (model=%s)", url, self.model)

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            logger.error("Vision API request failed: %s", e)
            return {}
        except Exception as e:
            logger.error("Unexpected error calling Vision API: %s", e)
            return {}

        # Extract the response content
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error("Unexpected API response structure: %s", e)
            logger.debug("Full response: %s", result)
            return {}

        # Parse JSON from the response (handle markdown code blocks)
        return _parse_response(content)

    def is_above_threshold(self, result: dict[str, Any]) -> bool:
        """Check if a recognition result meets the confidence threshold."""
        confidence = result.get("confidence", 0.0)
        try:
            return float(confidence) >= self.confidence_threshold
        except (TypeError, ValueError):
            return False


def _parse_response(content: str) -> dict[str, Any]:
    """Parse Vision LLM response into structured dict.

    Handles raw JSON or JSON wrapped in markdown code blocks.
    """
    text = content.strip()

    # Strip markdown code block if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [
            line for line in lines
            if not line.strip().startswith("```")
        ]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        logger.warning("Failed to parse Vision API response as JSON")
        logger.debug("Raw response: %s", text[:500])

    return {}


def create_client_from_config(config: dict) -> VisionClient | None:
    """Create a VisionClient from config.yaml vision section.

    Returns None if vision is disabled.
    """
    import os

    vision_config = config.get("vision", {})
    if not vision_config.get("enabled", False):
        return None

    api_key = os.environ.get("VISION_API_KEY", "lm-studio")

    return VisionClient(
        api_base=vision_config.get("api_base", "http://localhost:1234/v1"),
        api_key=api_key,
        model=vision_config.get("model", "qwen2.5-vl-7b"),
        confidence_threshold=vision_config.get("confidence_threshold", 0.8),
    )
