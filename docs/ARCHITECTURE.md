# Architecture & Project Structure

## Overview

**DMS Summarize** adalah aplikasi **document summarization** yang mengintegrasikan:
- **OCR multimodal** (text + image-based PDFs)
- **Multilingual support** (auto-detect bahasa)
- **LangChain chains** (bukan agents) untuk linear processing

**Stack:**
- Backend: FastAPI
- LLM: Configurable (Ollama, Gemini)
- LLM Vision: Google Gemini 2.0 Flash (untuk OCR)
- Text Splitting: LangChain RecursiveCharacterTextSplitter

---

## Directory Structure

```
app/
├── core/                          # Shared utilities (LLM factory, memory)
│   ├── models.py                  # get_chat_model() - LLM factory
│   └── memory.py                  # InMemorySaver
│
├── document/                      # Document loading & OCR (separate concern)
│   ├── loader.py                  # PyPDFLoader + OCR fallback
│   └── ocr.py                     # Gemini Vision / Tesseract abstraction
│
├── summarization/                 # All LLM-related work (chains + language)
│   ├── chains.py                  # LangChain chains + language detection
│   └── prompts.py                 # Prompt management
│
├── schemas/                       # Pydantic models
├── api/routes/summarize.py        # FastAPI POST /api/v1/summarize
├── config.py                      # Settings (from .env)
└── main.py                        # FastAPI app factory
```

**Key improvement:** Language detection (langdetect) is NOW IN `summarization/chains.py`, not a separate module. This simplifies imports and makes language awareness transparent to the pipeline.

---

## Data Flow: API Request → Response

### 1. HTTP Request

```
POST /api/v1/summarize
Content-Type: multipart/form-data
Body: {file: <pdf or docx>}
```

### 2. Route Handler (app/api/routes/summarize.py)

```python
@router.post("/summarize")
async def summarize(file: UploadFile):
    # 1. Validate file type
    # 2. Save to disk (temp)
    # 3. Call summarize_document()
    # 4. Clean up file
    # 5. Return JSON response
```

### 3. Document Processing Pipeline

```
summarize_document(file_path)
  ├─ [Step 1] load_and_split(file_path)
  │   ├─ Try: PyPDFLoader (text extraction)
  │   │   └─ If: text < 100 chars → image-based PDF
  │   ├─ Fallback: extract_text_from_pdf_pages() [Gemini Vision OCR]
  │   │   └─ pdf2image: convert each page → PIL.Image
  │   │   └─ GeminiVisionOCR.extract_text_from_image() [parallel or sequential]
  │   │   └─ Combine text from all pages
  │   └─ RecursiveCharacterTextSplitter: chunk text → List[Document]
  │
  ├─ [Step 2] detect_language(first_chunk_text)
  │   ├─ langdetect.detect(text) → lang_code ('id', 'en', 'th', etc)
  │   └─ build_multilingual_prompt_instruction(lang_code)
  │
  ├─ [Step 3] Choose chain based on chunk count
  │   ├─ If chunks ≤ 3 → _stuff_summarize()
  │   │   └─ Concatenate all chunks
  │   │   └─ Send to LLM in single call (STUFF chain)
  │   │
  │   └─ Else → _map_reduce_summarize()
  │       ├─ MAP: for each chunk → mini-summary (LLM call)
  │       └─ REDUCE: combine all → final summary (LLM call)
  │
  └─ [Step 4] Parse & validate
      ├─ RobustJsonParser.parse() → repair malformed JSON
      └─ _parse_result() → SummaryResult (Pydantic model)
```

### 4. Response

```json
{
  "status": "success",
  "filename": "invoice.pdf",
  "result": {
    "summary": "Dokumen ini adalah faktur...",
    "key_details": [
      {"label": "Nomor", "value": "INV-2026-001"},
      {"label": "Tanggal", "value": "21 April 2026"}
    ]
  }
}
```

---

## Key Design Decisions

### 1. **Unified Pipeline (Not 2 Capabilities)**

**Problem:** What if PDF has mixed content (text + images with important text)?

**Solution:**
```
┌────────────────────┐
│ PDF (any type)     │
└────────┬───────────┘
         │
    ┌────┴─────────────────┐
    ▼                       ▼
 Text-based              Image-based
 (PyPDFLoader)           (Gemini Vision)
    │                       │
    └─────────┬─────────────┘
              ▼
    Unified chunked text
              │
              ▼
   Language detection
              │
              ▼
    Summarize (in input language)
```

**Why:**
- Single code path → fewer bugs
- Handles all PDF types automatically
- No user decision required

**Future enhancement:** Also extract embedded images from mixed PDFs (currently text-based PDFs skip images)

### 2. **Chains vs Agents**

| Aspect | Chains | Agents |
|--------|--------|--------|
| Flow | Linear, deterministic | Loop with tool-calling |
| Tools | None (or simple | Multiple tools, reasoning |
| Use case | Document processing | Complex multi-step tasks |
| Cost | Lower (fewer LLM calls) | Higher (more calls) |

**Our choice: CHAINS** ✓
- Summarization is linear: load → chunk → LLM → output
- No tool-calling or multi-step reasoning needed
- Agents would add complexity without benefit

### 3. **OCR Abstraction (Factory Pattern)**

```python
# Easy to switch providers
ocr = get_ocr_provider("gemini")  # or "tesseract"
text = await ocr.extract_text_from_image(image)
```

**Why:**
- Config-driven: switch via `.env` or code
- Production can use different provider than dev
- No tight coupling to specific OCR service

### 4. **Language-Aware Prompts**

```python
lang_code = detect_language(text)
instruction = build_multilingual_prompt_instruction(lang_code)
# Appends to system prompt: "Respond in [language]"
```

**Why:**
- LLM respects language instruction
- Output matches input language automatically
- No translation needed

### 5. **Modular Directory Structure**

```
document/   - Everything about loading documents
language/   - Everything about language
summarization/ - Everything about summarization
core/       - Shared utilities (minimal)
api/        - HTTP endpoints
```

**Benefits:**
- Easy to find code
- Single Responsibility
- Reusable modules
- Clear import paths

---

## Configuration

All settings via `.env`:

```dotenv
# LLM (summarization)
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3-flash-preview
LLM_API_KEY=<secret>
LLM_TEMPERATURE=0.5
LLM_MAX_TOKEN=2048

# OCR (image-based PDFs)
OCR_PROVIDER=gemini          # switch to 'tesseract' for local

# App
APP_HOST=0.0.0.0
APP_PORT=8000
APP_LOG_LEVEL=info

# Document processing
UPLOAD_DIR=./uploads
MAX_CHUNK_SIZE=2000
CHUNK_OVERLAP=100
```

---

## Important Notes

### Testing
```bash
# Full test suite
pytest tests/test_ocr_multilingual.py -v

# Specific test
pytest tests/test_ocr_multilingual.py::TestLanguageDetection -v
```

### Logging
Enable debug logs:
```bash
APP_LOG_LEVEL=debug python -m uvicorn app.main:app
```

### LangChain Chains Explanation
A LangChain Chain is a sequence of operations:
```python
chain = prompt | llm | output_parser
result = await chain.ainvoke({"text": input})
```

It's synchronous/composable and **not** the same as LangChain Agents.

### Token Usage Monitoring
- Check Gemini API billing for Vision token costs
- Tesseract is free but less accurate
- Consider fallback strategy for cost optimization

---

## Future Enhancements

1. **Image Extraction from Mixed PDFs**
   - Extract images from PDF directly
   - OCR each image
   - Combine with text

2. **Per-Page Language Detection**
   - For truly mixed-language documents
   - Detect language per page

3. **Table & Chart Extraction**
   - Gemini Vision already supports this
   - Structured output (JSON/HTML)

4. **Document Classification**
   - Detect document type (invoice, contract, etc)
   - Apply domain-specific prompts

5. **Caching & Batch Processing**
   - Cache OCR results
   - Batch summarization for cost optimization

---

## Security & Privacy

### Credentials
- All secrets via environment variables (`.env`)
- No hardcoded API keys
- Pydantic-settings handles validation

### Data Handling
- Files saved to `UPLOAD_DIR` temporarily
- Deleted after processing
- No persistence unless explicitly saved

### PII Concerns
- Gemini Vision processes images (check data policy)
- For sensitive documents, use local Tesseract

---

Untuk detail lebih lanjut, lihat [OCR_MULTILINGUAL.md](./OCR_MULTILINGUAL.md).
