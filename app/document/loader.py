import logging
import os
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_core.documents import Document

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


async def load_and_split(file_path: str) -> list[Document]:
    """
    Load a document and split it into chunks.

    Strategy for PDFs:
    - Extract text page-by-page with PyPDF.
    - For any page with too little text (likely scanned), run OCR on that page.
    - This handles text-only, image-only, and mixed PDFs correctly.

    DOCX files are loaded directly with Docx2txtLoader.
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".docx":
        docs = Docx2txtLoader(file_path).load()
        if not docs or not any(d.page_content.strip() for d in docs):
            raise ValueError("DOCX appears to be empty.")
        return _split(docs)

    if ext == ".pdf":
        return await _load_pdf(file_path)

    raise ValueError(f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")


async def _load_pdf(file_path: str) -> list[Document]:
    """Load PDF with per-page OCR fallback for scanned pages."""
    from pdf2image import convert_from_path
    from app.document.ocr import get_ocr_provider

    # Load all pages via PyPDF first
    try:
        pdf_docs = PyPDFLoader(file_path).load()
    except Exception as e:
        logger.warning(f"PyPDFLoader failed: {e}. Will OCR all pages.")
        pdf_docs = []

    # Convert to images for per-page OCR fallback
    try:
        images = convert_from_path(file_path)
    except Exception as e:
        raise ValueError(f"Cannot read PDF file (may be corrupt): {e}")

    if not images:
        raise ValueError("PDF has no pages.")

    ocr = None  # lazy init — only create if needed
    page_texts = []

    for i, image in enumerate(images):
        # Get text extracted by PyPDF for this page (if available)
        pypdf_text = ""
        if i < len(pdf_docs):
            pypdf_text = pdf_docs[i].page_content.strip()

        if len(pypdf_text) >= 50:
            # Page has enough text — use PyPDF result
            page_texts.append(f"--- Page {i + 1} ---\n{pypdf_text}")
            logger.debug(f"Page {i + 1}: PyPDF ({len(pypdf_text)} chars)")
        else:
            # Page is likely scanned — OCR it
            if ocr is None:
                ocr = get_ocr_provider()
                logger.info(f"OCR provider initialized for scanned pages")
            try:
                ocr_text = await ocr.extract_text(image)
                if ocr_text:
                    page_texts.append(f"--- Page {i + 1} ---\n{ocr_text}")
                    logger.debug(f"Page {i + 1}: OCR ({len(ocr_text)} chars)")
                else:
                    logger.warning(f"Page {i + 1}: OCR returned empty text")
                    page_texts.append(f"--- Page {i + 1} ---\n[empty]")
            except Exception as e:
                logger.error(f"Page {i + 1}: OCR failed: {e}")
                page_texts.append(f"--- Page {i + 1} ---\n[OCR failed]")

    combined = "\n\n".join(page_texts)
    if not combined.strip():
        raise ValueError("Could not extract any text from PDF.")

    logger.info(f"PDF loaded: {len(images)} pages, {len(combined)} total chars")
    return _split([Document(page_content=combined, metadata={"source": file_path})])


def _split(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.max_chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(docs)


async def save_upload(file_bytes: bytes, filename: str) -> str:
    """Save uploaded file bytes to the uploads directory. Returns the saved path."""
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = Path(filename).name  # strip any path components
    dest = os.path.join(upload_dir, safe_name)
    with open(dest, "wb") as f:
        f.write(file_bytes)
    return dest



