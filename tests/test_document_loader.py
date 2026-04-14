import os
import tempfile
import pytest

from app.core.document_loader import load_and_split, ALLOWED_EXTENSIONS


@pytest.fixture
def sample_txt(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("Hello world. This is a test document.")
    return str(p)


def test_allowed_extensions():
    assert ".pdf" in ALLOWED_EXTENSIONS
    assert ".docx" in ALLOWED_EXTENSIONS


def test_unsupported_extension(sample_txt):
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_and_split(sample_txt)
