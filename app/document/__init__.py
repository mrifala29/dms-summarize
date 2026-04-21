"""Document processing module: loading, OCR, and chunking."""

from app.document.loader import load_and_split, save_upload, ALLOWED_EXTENSIONS
from app.document.ocr import get_ocr_provider

__all__ = [
    "load_and_split",
    "save_upload",
    "ALLOWED_EXTENSIONS",
    "get_ocr_provider",
]
