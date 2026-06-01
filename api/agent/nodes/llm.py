from langchain_openai import ChatOpenAI
from agent.config import load_settings


def get_llm() -> ChatOpenAI:
    settings = load_settings()
    if settings.llm_provider == "solar":
        return ChatOpenAI(
            model=settings.solar_model,
            api_key=settings.solar_api_key,
            base_url=settings.solar_base_url,
            temperature=0.3,
        )
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0.3,
    )
