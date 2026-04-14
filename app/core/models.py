from langchain_openai import ChatOpenAI

from app.config import llm_settings


def get_chat_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=llm_settings.llm_model,
        api_key=llm_settings.llm_api_key,
        base_url=llm_settings.llm_base_url,
        temperature=llm_settings.llm_temperature,
        max_tokens=llm_settings.llm_max_token,
    )
