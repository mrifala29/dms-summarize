from fastapi import FastAPI

from app.api.routes.summarize import router as summarize_router

app = FastAPI(
    title="DMS Summarize API",
    version="0.1.0",
    docs_url="/docs",
)

app.include_router(summarize_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
