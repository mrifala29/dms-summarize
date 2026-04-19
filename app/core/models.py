from typing import Union
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import llm_settings


def get_chat_model() -> Union[ChatOpenAI, ChatGoogleGenerativeAI]:
    """
    Factory function to get the appropriate LLM client based on provider config.
    
    Supports:
    - 'ollama': OpenAI-compatible local or remote endpoint
    - 'gemini': Google Generative AI (Gemini)
    """
    provider = llm_settings.llm_provider.lower()
    
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=llm_settings.llm_model,
            api_key=llm_settings.llm_api_key,
            temperature=llm_settings.llm_temperature,
            max_output_tokens=llm_settings.llm_max_token,
        )
    elif provider == "ollama":
        return ChatOpenAI(
            model=llm_settings.llm_model,
            api_key=llm_settings.llm_api_key or "dummy",  # Ollama doesn't require API key
            base_url=llm_settings.llm_base_url,
            temperature=llm_settings.llm_temperature,
            max_tokens=llm_settings.llm_max_token,
        )
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: 'ollama', 'gemini'"
        )
