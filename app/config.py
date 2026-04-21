from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "info"

    upload_dir: str = "./uploads"
    max_chunk_size: int = 2000
    chunk_overlap: int = 100

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


class LLMSettings(BaseSettings):
    """LLM Configuration
    
    Supported providers:
    - 'gemini': Google Generative AI
    - 'openai-compatible': OpenAI-compatible API (DeepSeek, etc.)
    """
    llm_provider: str = "gemini"  # 'gemini' or 'openai-compatible'
    llm_model: str = "gemini-2.0-flash"
    llm_api_key: str = "<LLM_API_KEY>"
    llm_base_url: str = ""  # Required for openai-compatible
    llm_temperature: float = 0.5
    llm_max_token: int = 2048

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


class OCRSettings(BaseSettings):
    """OCR Configuration for image-based PDFs"""
    ocr_provider: str = "easyocr"  # 'easyocr' (free, recommended), 'gemini' (paid), 'tesseract' (free, lower acc)
    ocr_api_key: str = ""  # Gemini API key for OCR (only needed if ocr_provider=gemini)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
llm_settings = LLMSettings()
ocr_settings = OCRSettings()
