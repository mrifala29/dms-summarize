"""
OCR providers for extracting text from images/scanned PDFs.

Providers:
  - gemini   : Google Gemini VLM (uses LLM_API_KEY from .env) - recommended
  - easyocr  : Local, free, multilingual
  - tesseract: Local, free, requires tesseract-ocr system package

Set OCR_PROVIDER in .env to choose (default: gemini).
"""

import base64
import io
import logging
from abc import ABC, abstractmethod

from PIL import Image

from app.config import ocr_settings, llm_settings

logger = logging.getLogger(__name__)


class OCRProvider(ABC):
    @abstractmethod
    async def extract_text(self, image: Image.Image) -> str:
        pass


class GeminiVisionOCR(OCRProvider):
    def __init__(self):
        api_key = llm_settings.llm_api_key
        if not api_key:
            raise ValueError("LLM_API_KEY is required for Gemini OCR.")
        if api_key.startswith("sk-"):
            raise ValueError("LLM_API_KEY is an OpenAI key; Gemini needs AIza... key.")
        from langchain_google_genai import ChatGoogleGenerativeAI
        self.llm = ChatGoogleGenerativeAI(model=llm_settings.llm_model, api_key=api_key, temperature=0)
        logger.info(f"Initialized Gemini Vision OCR with model: {llm_settings.llm_model}")

    async def extract_text(self, image: Image.Image) -> str:
        import io as _io
        buffered = _io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        from langchain_core.messages import HumanMessage
        msg = HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": (
                "Extract ALL visible text from this image exactly as written. "
                "Preserve layout, headers, labels and values. "
                "If text is in multiple languages, extract all of them. "
                "Return ONLY the extracted text."
            )},
        ])
        response = await self.llm.ainvoke([msg])
        
        # Handle both string and list responses from LLM
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        return str(content).strip()


class EasyOCR(OCRProvider):
    def __init__(self, languages: list = None):
        try:
            import easyocr
            self.reader = easyocr.Reader(languages or ["en", "th", "id", "vi"], gpu=False)
        except ImportError:
            raise ImportError("easyocr not installed. Run: pip install easyocr")
        logger.info(f"EasyOCR initialized for: {languages}")

    async def extract_text(self, image: Image.Image) -> str:
        import numpy as np
        results = self.reader.readtext(np.array(image))
        return "\n".join(r[1] for r in results).strip()


class TesseractOCR(OCRProvider):
    def __init__(self):
        try:
            import pytesseract
            self.pytesseract = pytesseract
        except ImportError:
            raise ImportError("pytesseract not installed. Run: pip install pytesseract")
        logger.info("Initialized Tesseract OCR")

    async def extract_text(self, image: Image.Image) -> str:
        return self.pytesseract.image_to_string(image).strip()


def get_ocr_provider(provider_name: str = None) -> OCRProvider:
    name = (provider_name or ocr_settings.ocr_provider).lower()
    if name == "gemini":
        return GeminiVisionOCR()
    if name == "easyocr":
        return EasyOCR()
    if name == "tesseract":
        return TesseractOCR()
    raise ValueError(f"Unknown OCR provider: {name!r}. Choose: gemini, easyocr, tesseract")
