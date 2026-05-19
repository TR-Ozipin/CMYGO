"""Tests for Vision LLM client and caching."""

from unittest.mock import patch

from src.vision import (
    VisionClient,
    _parse_response,
    compute_image_hash,
    create_client_from_config,
)
from src.database import (
    init_db,
    get_vision_cache,
    save_vision_cache,
)


class TestParseResponse:
    """Test Vision LLM response parsing."""

    def test_parse_raw_json(self):
        content = '{"booth": "A01", "circle_name": "Test", "confidence": 0.9}'
        result = _parse_response(content)
        assert result["booth"] == "A01"
        assert result["confidence"] == 0.9

    def test_parse_markdown_wrapped_json(self):
        content = '```json\n{"booth": "A01", "circle_name": "Test"}\n```'
        result = _parse_response(content)
        assert result["booth"] == "A01"

    def test_parse_invalid_json(self):
        content = "This is not JSON at all"
        result = _parse_response(content)
        assert result == {}

    def test_parse_empty_string(self):
        result = _parse_response("")
        assert result == {}

    def test_parse_json_with_null_fields(self):
        content = '{"booth": null, "circle_name": "Test", "confidence": 0.5}'
        result = _parse_response(content)
        assert result["booth"] is None
        assert result["circle_name"] == "Test"

    def test_parse_json_with_japanese(self):
        content = '{"booth": "水 西あ52ab", "circle_name": "サークル名"}'
        result = _parse_response(content)
        assert result["booth"] == "水 西あ52ab"
        assert result["circle_name"] == "サークル名"


class TestVisionClient:
    """Test VisionClient behavior."""

    def test_is_above_threshold(self):
        client = VisionClient(confidence_threshold=0.8)
        assert client.is_above_threshold({"confidence": 0.9}) is True
        assert client.is_above_threshold({"confidence": 0.8}) is True
        assert client.is_above_threshold({"confidence": 0.7}) is False
        assert client.is_above_threshold({"confidence": None}) is False
        assert client.is_above_threshold({}) is False

    def test_default_config(self):
        client = VisionClient()
        assert "localhost:1234" in client.api_base
        assert client.model == "qwen2.5-vl-7b"
        assert client.confidence_threshold == 0.8


class TestVisionCache:
    """Test vision result caching in SQLite."""

    def test_cache_roundtrip(self, tmp_path):
        db_path = tmp_path / "test.db"
        init_db(db_path)

        test_result = {
            "booth": "A01",
            "circle_name": "TestCircle",
            "confidence": 0.92,
        }

        save_vision_cache(db_path, "abc123hash", test_result)
        cached = get_vision_cache(db_path, "abc123hash")

        assert cached is not None
        assert cached["booth"] == "A01"
        assert cached["confidence"] == 0.92

    def test_cache_miss(self, tmp_path):
        db_path = tmp_path / "test.db"
        init_db(db_path)

        result = get_vision_cache(db_path, "nonexistent_hash")
        assert result is None

    def test_cache_overwrite(self, tmp_path):
        db_path = tmp_path / "test.db"
        init_db(db_path)

        save_vision_cache(db_path, "hash1", {"booth": "A01", "confidence": 0.5})
        save_vision_cache(db_path, "hash1", {"booth": "B02", "confidence": 0.9})

        cached = get_vision_cache(db_path, "hash1")
        assert cached["booth"] == "B02"


class TestComputeImageHash:
    """Test image hash computation."""

    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "img1.jpg"
        f2 = tmp_path / "img2.jpg"
        content = b"fake image content"
        f1.write_bytes(content)
        f2.write_bytes(content)

        assert compute_image_hash(f1) == compute_image_hash(f2)

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "img1.jpg"
        f2 = tmp_path / "img2.jpg"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")

        assert compute_image_hash(f1) != compute_image_hash(f2)


class TestCreateClientFromConfig:
    """Test config-based client creation."""

    def test_disabled_returns_none(self):
        config = {"vision": {"enabled": False}}
        assert create_client_from_config(config) is None

    def test_no_vision_config_returns_none(self):
        config = {}
        assert create_client_from_config(config) is None

    def test_enabled_creates_client(self):
        config = {
            "vision": {
                "enabled": True,
                "api_base": "http://localhost:1234/v1",
                "model": "test-model",
                "confidence_threshold": 0.7,
            }
        }
        with patch.dict("os.environ", {"VISION_API_KEY": "test-key"}):
            client = create_client_from_config(config)
        assert client is not None
        assert client.model == "test-model"
        assert client.confidence_threshold == 0.7
