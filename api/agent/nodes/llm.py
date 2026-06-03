from langchain_openai import ChatOpenAI
from agent.config import load_settings


def get_llm(temperature: float = 0.3, model: str | None = None) -> ChatOpenAI:
    """기본 채팅 LLM. streaming=True 로 stream_mode='messages' 토큰 흐름을 보장한다."""
    settings = load_settings()
    if settings.llm_provider == "solar":
        return ChatOpenAI(
            model=model or settings.solar_model,
            api_key=settings.solar_api_key,
            base_url=settings.solar_base_url,
            temperature=temperature,
            streaming=True,
        )
    return ChatOpenAI(
        model=model or "gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=temperature,
        streaming=True,
    )


def get_intent_llm() -> ChatOpenAI:
    """의도 분석 전용 LLM: 결정성을 위해 temperature=0, 모델은 INTENT_MODEL 로 교체 가능."""
    settings = load_settings()
    return get_llm(temperature=0.0, model=settings.intent_model)
