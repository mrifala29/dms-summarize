import os

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.document_loader import save_upload, ALLOWED_EXTENSIONS
from app.core.summarizer import summarize_document
from app.schemas.summarize import SummarizeResponse

router = APIRouter(prefix="/api/v1", tags=["summarize"])


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    file_path = await save_upload(contents, file.filename or "document" + ext)

    try:
        result = await summarize_document(file_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if os.path.exists(file_path):
            os.unlink(file_path)

    return SummarizeResponse(
        status="success",
        filename=file.filename or "",
        result=result,
    )
