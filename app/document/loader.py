import os
import tempfile
import logging
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_core.documents import Document

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _get_loader(file_path: str):
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return PyPDFLoader(file_path)
    if ext == ".docx":
        return Docx2txtLoader(file_path)
    raise ValueError(f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")


async def load_and_split(file_path: str) -> list:
    """
    Load document and split into chunks.
    
    Unified pipeline supports:
    1. Text-based PDFs (PyPDFLoader)
    2. Image-based PDFs (Gemini Vision OCR fallback)
    3. Mixed PDFs (text + images)
    4. DOCX files
    
    Args:
        file_path: Path to document file
        
    Returns:
        List of Document chunks
        
    Raises:
        ValueError: If document is empty after all extraction attempts
    """
    ext = Path(file_path).suffix.lower()
    documents = []
    
    # Step 1: Try standard text extraction (PyPDFLoader / Docx2txtLoader)
    try:
        loader = _get_loader(file_path)
        documents = loader.load()
        
        # Check if PDF has extractable text
        if ext == ".pdf" and documents:
            total_chars = sum(len(doc.page_content.strip()) for doc in documents)
            if total_chars < 100:  # Threshold: likely image-based
                logger.warning(
                    f"PDF has very little text ({total_chars} chars), "
                    "likely image-based. Will attempt OCR..."
                )
                documents = []  # Force OCR fallback
            else:
                logger.info(f"Extracted {total_chars} chars from PDF using PyPDFLoader")
    except Exception as e:
        logger.warning(f"Standard text extraction failed: {e}")
    
    # Step 2: Fallback to OCR if needed (image-based PDF)
    # Note: Future enhancement - also extract embedded images from mixed PDFs
    if ext == ".pdf" and not documents:
        logger.info("Attempting OCR for image-based PDF...")
        try:
            from app.document.ocr import extract_text_from_pdf_pages
            ocr_text = await extract_text_from_pdf_pages(file_path, provider=None)
            
            if ocr_text.strip():
                documents = [Document(page_content=ocr_text, metadata={"source": file_path})]
                logger.info("OCR extraction successful")
            else:
                raise ValueError("OCR produced no text")
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            # Will raise ValueError below if documents still empty
    
    # Step 3: Validate and chunk
    if not documents:
        raise ValueError(
            "Document is empty or could not be parsed. "
            "Tried: text extraction (PyPDFLoader), OCR (Gemini Vision). "
            "Ensure PDF is valid and not corrupted."
        )
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.max_chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


async def save_upload(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    os.makedirs(settings.upload_dir, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        dir=settings.upload_dir, suffix=ext, delete=False
    )
    tmp.write(file_bytes)
    tmp.close()
    return tmp.name
