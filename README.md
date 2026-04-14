# DMS Summarize

AI-powered document summarization for DMS App — extracts **Summary** and **Key Details** from employee contracts and other HR documents (PDF / DOCX).

## Structure

```
dms-summarize/
├── app/
│   ├── main.py                 # FastAPI entry
│   ├── config.py               # Settings (.env)
│   ├── api/routes/
│   │   └── summarize.py        # POST /api/v1/summarize
│   ├── core/
│   │   ├── models.py           # Model factory (Ollama / Gemini)
│   │   ├── document_loader.py  # PDF & DOCX loader + chunking
│   │   └── summarizer.py       # LangChain summarize chain
│   └── schemas/
│       └── summarize.py        # Pydantic response models
├── tests/
│   ├── test_api.py
│   ├── test_document_loader.py
│   └── test_summarizer.py
├── .env.example
├── requirements.txt
└── README.md
```

## Quick Start

```bash
# 1. Clone & enter
cd dms-summarize

# 2. Virtual env
python -m venv .venv && source .venv/bin/activate

# 3. Install deps
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env — set MODEL_PROVIDER and model-specific keys
```

### Option A — Ollama (local, free)

```bash
# Install Ollama: https://ollama.com
ollama pull llama3
# .env: MODEL_PROVIDER=ollama
```

### Option B — Gemini (free tier)

```bash
# Get API key: https://aistudio.google.com/apikey
# .env: MODEL_PROVIDER=gemini, GEMINI_API_KEY=<your-key>
```

### Run

```bash
uvicorn app.main:app --reload
# Open http://localhost:8000/docs
```

### Test

```bash
pytest -q
```

## API

### `POST /api/v1/summarize`

Upload a PDF or DOCX file → returns summary + key details.

**Request**: `multipart/form-data` with `file` field.

**Response**:
```json
{
  "status": "success",
  "filename": "contract.pdf",
  "result": {
    "summary": "This is a fixed-term employee contract between ...",
    "key_details": [
      {"label": "Employee Name", "value": "John Doe"},
      {"label": "Position", "value": "Software Engineer"},
      {"label": "Contract Type", "value": "Fixed-term"},
      {"label": "Start Date", "value": "2026-01-01"},
      {"label": "End Date", "value": "2027-01-01"}
    ]
  }
}
```

## How It Works

1. **Upload** — file saved temporarily, validated (PDF/DOCX only).
2. **Load & Chunk** — `PyPDFLoader` / `Docx2txtLoader` + `RecursiveCharacterTextSplitter`.
3. **Summarize** — if document is small (≤3 chunks), uses **stuff** strategy (single LLM call). For larger documents, uses **map-reduce** (chunk → partial summary → combine).
4. **Structured output** — LLM returns JSON with `summary` and `key_details`.
5. **Cleanup** — temp file deleted after processing.

## MCP (Optional)

For up-to-date LangChain docs inside Copilot, install the [LangChain Docs MCP server](https://docs.langchain.com/use-these-docs).
