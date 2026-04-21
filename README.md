# DMS Summarize

AI-powered document summarization service for document management systems. Extracts **Summary** and **Key Details** from corporate legal documents, including scanned/image-based PDFs with automatic language detection.

**Supports:** contracts, agreements, MoU, NDA, employment contracts, lease agreements, board resolutions, procurement documents, and other corporate instruments.

**Features:**
- 📄 **OCR**: Automatic text extraction from scanned PDFs (Gemini Vision)
- 🌍 **Multilingual**: Auto-detects document language, summarizes in same language
- ⚡ **Fast**: LangChain chains (STUFF/MAP-REDUCE) for efficient processing
- 📊 **Structured Output**: JSON with summary + key details
- 🔧 **Flexible LLMs**: Supports Gemini, DeepSeek (OpenAI-compatible), or any OpenAI-compatible API

---

## Quick Start

### 1. Setup

```bash
# Clone
git clone <repo> && cd dms-summarize

# Virtual environment
python -m venv .venv && source .venv/bin/activate

# Install
pip install -r requirements.txt
```

### 2. Configure `.env`

Two options:

**Option A: Gemini (recommended for small teams)**

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.0-flash
LLM_API_KEY=<your-gemini-api-key>
```

**Option B: DeepSeek via MaiaRouter (recommended for production)**

```env
LLM_PROVIDER=openai-compatible
LLM_MODEL=deepseek/deepseek-chat
LLM_API_KEY=<your-maiarouter-api-key>
LLM_BASE_URL=https://api.maiarouter.ai/v1
```

See [SETUP_DEEPSEEK.md](SETUP_DEEPSEEK.md) for detailed configuration.

### 3. Run

```bash
uvicorn app.main:app --reload
# Open http://localhost:8000/docs
```

### 4. Test

```bash
python -m pytest tests/test_ocr_multilingual.py -v
```

---

## API Endpoint

### `POST /api/v1/summarize`

Upload document → returns summary + key details.

**Request:** `multipart/form-data` with `file` field (PDF/DOCX)

**Response:**
```json
{
  "status": "success",
  "filename": "contract.pdf",
  "result": {
    "summary": "This employment contract between Employer and Employee specifies...",
    "key_details": [
      {"label": "Type", "value": "Employment Agreement (PKWT)"},
      {"label": "Parties", "value": "PT ABC and John Doe"},
      {"label": "Position", "value": "Software Engineer"},
      {"label": "Salary", "value": "IDR 150,000,000/year"},
      {"label": "Duration", "value": "2 years"},
      {"label": "Language", "value": "Indonesian"}
    ]
  }
}
```

---

## How It Works

```
1. File Upload
   ↓
2. Load & Extract Text (PyPDFLoader or OCR)
   ├─ If text-based PDF → extract text
   └─ If scanned/image PDF → use Gemini Vision OCR
   ↓
3. Language Detection (langdetect)
   → Auto-detect language (th, id, en, vi, etc.)
   ↓
4. Chunking (RecursiveCharacterTextSplitter)
   → Split into manageable chunks
   ↓
5. Summarization (LangChain)
   ├─ Small docs (≤3 chunks) → STUFF (single call)
   └─ Large docs (>3 chunks) → MAP-REDUCE (map per chunk + reduce)
   ↓
6. Structured Output (JSON)
   → Summary + Key Details (in detected language)
   ↓
7. Cleanup & Response
   → Delete temp file, return JSON
```

---

## Features

| Feature | Details |
|---|---|
| **OCR** | Gemini Vision for scanned/image-based PDFs |
| **Multilingual** | Auto-detects language, outputs in same language |
| **Document Types** | Contracts, agreements, corporate documents, legal instruments |
| **Efficiency** | STUFF/MAP-REDUCE chains for optimal token usage |
| **Structured Output** | JSON with summary + key details + metadata |
| **Error Handling** | Robust JSON parsing, OCR fallback, detailed logging |

---

## Architecture

- **Backend**: FastAPI + LangChain
- **LLM**: Gemini (default) or OpenAI-compatible (DeepSeek, etc.)
- **Document Processing**: pdf2image, PyPDF, python-docx
- **OCR**: Gemini Vision (separate from main LLM)
- **Language Detection**: langdetect (50+ languages)

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design.

---

## Troubleshooting

**Q: OCR fails on scanned PDF**
- A: Set `LLM_API_KEY` and ensure it's a valid Gemini API key. Check `.env`.

**Q: Output is in English, not original language**
- A: Language detection might fail if first chunk is too short. Add more text or set specific language in prompts.

**Q: API returns 500 error**
- A: Check logs with `tail -f /tmp/app.log` or watch console output. Share error message.

For more help, see [SETUP_DEEPSEEK.md](SETUP_DEEPSEEK.md).

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_ocr_multilingual.py::TestLanguageDetection::test_detect_thai -v

# Coverage
python -m pytest --cov=app tests/
```

All 15 tests should pass ✅

---

## License

MIT
