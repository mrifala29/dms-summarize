"""
OCR abstraction layer supporting multiple providers.

Providers:
  - easyocr: EasyOCR (free, local, high accuracy, multilingual) — RECOMMENDED
  - gemini: Google Gemini Vision (API-based, paid, very high accuracy)
  - tesseract: Tesseract OCR (free, local, medium accuracy)

Supports image-based PDFs and scanned documents.
"""

import base64
import logging
from abc import ABC, abstractmethod
from typing import Optional

from pdf2image import convert_from_path
from PIL import Image
import io

from app.config import ocr_settings

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class OCRProvider(ABC):
    """Base class for OCR providers."""
    
    @abstractmethod
    async def extract_text_from_image(self, image_input) -> str:
        """
        Extract text from an image (PIL Image or base64 string).
        Returns extracted text as string.
        """
        pass


class GeminiVisionOCR(OCRProvider):
    """Gemini Vision-based OCR provider.
    
    Uses OCR_API_KEY from .env (dedicated Gemini API key).
    If OCR_API_KEY is not set, falls back to LLM_API_KEY — only works
    if LLM_PROVIDER=gemini (Gemini-issued key, not MaiaRouter/DeepSeek).
    """
    
    def __init__(self):
        from app.config import ocr_settings, llm_settings
        
        # Prefer dedicated OCR key; fallback to main LLM key
        api_key = ocr_settings.ocr_api_key or llm_settings.llm_api_key
        
        if not api_key or api_key in ("<LLM_API_KEY>", ""):
            raise ValueError(
                "No Gemini API key found for OCR. "
                "Set OCR_API_KEY=<your-gemini-key> in .env. "
                "Get a key at: https://aistudio.google.com/apikey"
            )
        
        if api_key.startswith("sk-"):
            raise ValueError(
                "OCR_API_KEY looks like an OpenAI/MaiaRouter key (starts with 'sk-'). "
                "Gemini Vision requires a Google AI API key (starts with 'AIza...'). "
                "Set OCR_API_KEY=<your-gemini-key> in .env. "
                "Get a key at: https://aistudio.google.com/apikey"
            )
        
        from langchain_google_genai import ChatGoogleGenerativeAI
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            api_key=api_key,
            temperature=0,
        )
        logger.info("Initialized Gemini Vision for OCR")
    
    async def extract_text_from_image(self, image_input) -> str:
        """
        Use Gemini Vision to extract text from image.
        
        Args:
            image_input: PIL Image object or base64 string
            
        Returns:
            Extracted text
        """
        try:
            # Convert PIL Image to base64 if needed
            if isinstance(image_input, Image.Image):
                buffered = io.BytesIO()
                image_input.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            elif isinstance(image_input, str):
                img_base64 = image_input
            else:
                raise ValueError(f"Expected PIL Image or base64 str, got {type(image_input)}")
            
            prompt = (
                "Extract ALL visible text from this image exactly as written. "
                "Preserve all layout, spacing, formatting, headers, labels, and values. "
                "If text is in multiple languages, extract all of them. "
                "Return ONLY the extracted text, nothing else."
            )
            
            logger.debug(f"Calling Gemini Vision OCR")
            
            # Use LangChain message format (more reliable with LangChain)
            from langchain_core.messages import HumanMessage
            
            message = HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                    },
                    {"type": "text", "text": prompt},
                ]
            )
            
            response = await self.llm.ainvoke([message])
            text = response.content.strip()
            logger.debug(f"Gemini Vision extracted {len(text)} characters")
            return text
            
        except Exception as e:
            logger.error(f"Gemini Vision OCR failed: {type(e).__name__}: {str(e)}")
            raise


class EasyOCR(OCRProvider):
    """EasyOCR-based provider — free, multilingual, high accuracy.
    
    Excellent for Thai, Indonesian, Vietnamese, English, and 80+ other languages.
    Runs locally, no API quota limits. First use downloads model (~500MB).
    """
    
    def __init__(self, languages: list = None):
        """
        Initialize EasyOCR reader.
        
        Args:
            languages: List of language codes (e.g., ['th', 'en']).
                      If None, detects from document. Default: ['en']
        """
        try:
            import easyocr
            self.reader = easyocr.Reader(
                languages or ['en'],
                gpu=False,  # Use CPU; set True if CUDA available
            )
        except ImportError:
            raise ImportError(
                "easyocr not installed. Install with: pip install easyocr"
            )
        logger.info(f"Initialized EasyOCR for languages: {languages or ['en']}")
    
    async def extract_text_from_image(self, image_input) -> str:
        """
        Use EasyOCR to extract text from image.
        
        Args:
            image_input: PIL Image object
            
        Returns:
            Extracted text
        """
        try:
            if isinstance(image_input, str):
                # Base64 to PIL
                img_bytes = base64.b64decode(image_input)
                image_input = Image.open(io.BytesIO(img_bytes))
            
            if not isinstance(image_input, Image.Image):
                raise ValueError(f"Expected PIL Image, got {type(image_input)}")
            
            logger.debug(f"EasyOCR processing image {image_input.size}")
            
            # EasyOCR expects numpy array
            import numpy as np
            img_array = np.array(image_input)
            
            results = self.reader.readtext(img_array)
            
            # Combine all detected text
            text = "\n".join([result[1] for result in results])
            logger.debug(f"EasyOCR extracted {len(text)} characters")
            return text.strip()
            
        except Exception as e:
            logger.error(f"EasyOCR failed: {type(e).__name__}: {str(e)}")
            raise


class TesseractOCR(OCRProvider):
    """Tesseract-based OCR provider (local fallback)."""
    
    def __init__(self):
        try:
            import pytesseract
            self.pytesseract = pytesseract
        except ImportError:
            raise ImportError(
                "pytesseract not installed. Install with: pip install pytesseract. "
                "Also requires tesseract-ocr system package."
            )
    
    async def extract_text_from_image(self, image_input) -> str:
        """
        Use Tesseract to extract text from image.
        
        Args:
            image_input: PIL Image object
            
        Returns:
            Extracted text
        """
        if isinstance(image_input, str):
            # Base64 string → convert to PIL Image
            import base64
            img_bytes = base64.b64decode(image_input)
            image_input = Image.open(io.BytesIO(img_bytes))
        
        try:
            text = self.pytesseract.image_to_string(image_input)
            return text.strip()
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise


def get_ocr_provider(provider_name: str = None) -> OCRProvider:
    """
    Factory function to get OCR provider.
    
    Args:
        provider_name: 'easyocr' (free, recommended), 'gemini' (paid), 'tesseract' (free, lower acc)
                      or None to use config
        
    Returns:
        OCRProvider instance
        
    Raises:
        ValueError: If provider not supported or dependencies missing
    """
    if provider_name is None:
        provider_name = ocr_settings.ocr_provider
    
    provider_name = provider_name.lower()
    
    if provider_name == "easyocr":
        return EasyOCR(languages=['th', 'en', 'id', 'vi'])  # Thai, English, Indonesian, Vietnamese
    elif provider_name == "gemini":
        return GeminiVisionOCR()
    elif provider_name == "tesseract":
        return TesseractOCR()
    else:
        raise ValueError(
            f"Unsupported OCR provider: {provider_name}. "
            f"Supported: 'easyocr' (recommended), 'gemini', 'tesseract'"
        )


async def extract_text_from_pdf_pages(pdf_path: str, provider: str = None) -> str:
    """
    Convert PDF pages to images and extract text via OCR.
    
    This is used when PyPDFLoader cannot extract text (image-based PDFs).
    
    Args:
        pdf_path: Path to PDF file
        provider: OCR provider to use. If None, uses OCR_PROVIDER from config.
        
    Returns:
        Combined text from all pages
        
    Raises:
        ValueError: If PDF conversion or OCR extraction fails
    """
    if provider is None:
        provider = ocr_settings.ocr_provider
    
    ocr = get_ocr_provider(provider)
    all_text = []
    
    try:
        logger.info(f"Converting PDF to images: {pdf_path}")
        images = convert_from_path(pdf_path)
        
        if not images:
            raise ValueError(f"PDF conversion produced no pages. PDF may be corrupted.")
        
        logger.info(f"Converted {len(images)} pages to images for OCR (provider: {provider})")
        
        for idx, image in enumerate(images):
            try:
                logger.debug(f"OCR processing page {idx + 1}/{len(images)}")
                text = await ocr.extract_text_from_image(image)
                
                if not text:
                    logger.warning(f"Page {idx + 1}: OCR returned empty text")
                    all_text.append(f"--- Page {idx + 1} ---\n[OCR: Empty result]")
                else:
                    all_text.append(f"--- Page {idx + 1} ---\n{text}")
                    logger.debug(f"Page {idx + 1}: Extracted {len(text)} chars")
                    
            except Exception as e:
                logger.error(f"Page {idx + 1} OCR failed: {type(e).__name__}: {str(e)}")
                all_text.append(f"--- Page {idx + 1} ---\n[OCR failed: {type(e).__name__}]")
        
        combined = "\n\n".join(all_text)
        if not combined or "[OCR failed:" in combined:
            logger.error(f"OCR extraction incomplete. Text length: {len(combined)}")
        
        return combined
        
    except Exception as e:
        logger.error(f"PDF to image conversion failed: {type(e).__name__}: {str(e)}")
        raise ValueError(f"PDF processing failed: {str(e)}")
