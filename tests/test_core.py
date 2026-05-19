"""Tests for core utility functions."""

from src.core import extract_booth_from_filename
from src.rename import extract_twitter_id, replace_illegal_chars


class TestExtractTwitterId:
    """Test Twitter ID extraction from filenames."""

    def test_standard_format(self):
        assert extract_twitter_id(
            "twitter-someuser-123-456.jpg",
            r"twitter-([^-]+)-\d+-\d+",
        ) == "someuser"

    def test_case_insensitive_result(self):
        result = extract_twitter_id(
            "twitter-SomeUser-123-456.jpg",
            r"twitter-([^-]+)-\d+-\d+",
        )
        assert result == "someuser"

    def test_no_match(self):
        assert extract_twitter_id(
            "random_image.jpg",
            r"twitter-([^-]+)-\d+-\d+",
        ) is None

    def test_empty_filename(self):
        assert extract_twitter_id("", r"twitter-([^-]+)-\d+-\d+") is None

    def test_complex_username(self):
        result = extract_twitter_id(
            "twitter-user_name123-999-888.png",
            r"twitter-([^-]+)-\d+-\d+",
        )
        assert result == "user_name123"


class TestReplaceIllegalChars:
    """Test illegal filename character replacement."""

    def test_backslash(self):
        assert "＼" in replace_illegal_chars("test\\name")

    def test_colon(self):
        assert "：" in replace_illegal_chars("test:name")

    def test_question_mark(self):
        assert "？" in replace_illegal_chars("test?name")

    def test_no_illegal_chars(self):
        assert replace_illegal_chars("normal_name") == "normal_name"

    def test_multiple_illegal_chars(self):
        result = replace_illegal_chars('a/b:c*d')
        assert "/" not in result
        assert ":" not in result
        assert "*" not in result

    def test_japanese_text_unchanged(self):
        text = "水 西あ52ab サークル名"
        assert replace_illegal_chars(text) == text


class TestExtractBoothFromFilename:
    """Test booth extraction from renamed filenames."""

    def test_standard_booth(self):
        assert extract_booth_from_filename("水 西あ52ab サークル名.jpg") == "水"

    def test_booth_with_space(self):
        # extract_booth_from_filename splits on first space
        assert extract_booth_from_filename("A01 CircleName.jpg") == "A01"

    def test_empty_filename(self):
        assert extract_booth_from_filename("") is None

    def test_no_extension(self):
        assert extract_booth_from_filename("A01 Name") == "A01"
