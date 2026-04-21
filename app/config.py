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
    """LLM configuration. Supported providers: 'gemini', 'openai-compatible'."""
    llm_provider: str = "gemini"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""  # Required for openai-compatible
    llm_temperature: float = 0.5
    llm_max_token: int = 2048

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


class OCRSettings(BaseSettings):
    """OCR configuration. Providers: 'gemini' (VLM, uses LLM_API_KEY), 'easyocr', 'tesseract'."""
    ocr_provider: str = "gemini"  # 'gemini' recommended; 'easyocr' or 'tesseract' for local

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
llm_settings = LLMSettings()
ocr_settings = OCRSettings()
