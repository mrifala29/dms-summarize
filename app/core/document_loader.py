import os
import tempfile
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader

from app.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _get_loader(file_path: str):
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return PyPDFLoader(file_path)
    if ext == ".docx":
        return Docx2txtLoader(file_path)
    raise ValueError(f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")


def load_and_split(file_path: str) -> list:
    loader = _get_loader(file_path)
    documents = loader.load()

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
