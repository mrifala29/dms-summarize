from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "info"

    upload_dir: str = "./uploads"
    max_chunk_size: int = 4000
    chunk_overlap: int = 200

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


class LLMSettings(BaseSettings):
    llm_model: str = "qwen2.5:7b-instruct"
    llm_api_key: str = "<LLM_API_KEY>"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_temperature: float = 0.5
    llm_max_token: int = 256

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
llm_settings = LLMSettings()
