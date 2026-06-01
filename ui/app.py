import streamlit as st
import httpx
import os
import json
import logging
from datetime import datetime
from pathlib import Path

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
EXAMPLE_QUERIES_PATH = Path(__file__).with_name("example_queries.json")
STYLES_PATH = Path(__file__).with_name("styles.css")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("visaguide.ui")


def load_example_queries() -> list[str]:
    try:
        with EXAMPLE_QUERIES_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [q for q in data if isinstance(q, str) and q.strip()]
    except FileNotFoundError:
        logger.warning("Example queries file not found: %s", EXAMPLE_QUERIES_PATH)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in %s", EXAMPLE_QUERIES_PATH)
    except Exception:
        logger.exception("Failed to load example queries")

    return [
        "캐나다에서 소프트웨어 개발자로 취업하고 싶어요",
        "일본 유학 비자 받으려면 어떻게 해야 하나요?",
        "호주 워킹홀리데이 신청 방법 알려주세요",
        "미국 관광 비자로 입국 후 체류 연장이 가능한가요?",
        "독일 취업 비자 종류와 요건이 궁금해요",
        "영국 학생 비자 필요 서류 알려주세요",
    ]


def load_styles() -> None:
    try:
        css = STYLES_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Styles file not found: %s", STYLES_PATH)
        return
    except Exception:
        logger.exception("Failed to load styles")
        return

    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if "pending_input" not in st.session_state:
        st.session_state.pending_input = None


def reset_session_state() -> None:
    st.session_state.messages = []
    st.session_state.session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    st.session_state.pending_input = None


def render_sidebar(example_queries: list[str]) -> None:
    st.markdown("## 🛂 VisaGuide AI")
    st.markdown("---")
    st.markdown("### 지원 국가")
    st.markdown(
        "🇺🇸 미국 &nbsp; 🇯🇵 일본 &nbsp; 🇬🇧 영국\n\n"
        "🇨🇦 캐나다 &nbsp; 🇦🇺 호주 &nbsp; 🇩🇪 독일"
    )
    st.markdown("---")
    st.markdown("### 예시 질문")
    for i, q in enumerate(example_queries):
        if st.button(q, use_container_width=True, key=f"btn_{i}"):
            st.session_state["pending_input"] = q

    st.markdown("---")
    if st.button("대화 초기화", use_container_width=True):
        reset_session_state()
        st.rerun()

    st.markdown(
        '<div class="disclaimer-box">'
        "⚠️ 모든 비자 정보는 <b>참고용</b>이며, "
        "실제 신청 시 해당 국가 공식 기관(대사관·이민국)에서 "
        "최신 정보를 반드시 확인하세요."
        "</div>",
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown('<p class="visa-title">🛂 VisaGuide AI</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="visa-subtitle">FastAPI · LangGraph · RAG · Tool Calling — '
        "목적지·목적·기간 세 가지만 말씀해 주세요</p>",
        unsafe_allow_html=True,
    )


def render_initial_greeting() -> None:
    if not st.session_state.messages:
        with st.chat_message("assistant"):
            st.markdown(
                "안녕하세요! **VisaGuide AI**입니다. 🛂\n\n"
                "**어느 나라에서, 얼마나, 무슨 목적으로** 체류하실 계획인지 알려주세요. "
                "적합한 비자 정보를 찾아드리겠습니다.\n\n"
                "> 지원 국가: 🇺🇸 미국 · 🇯🇵 일본 · 🇬🇧 영국 · 🇨🇦 캐나다 · 🇦🇺 호주 · 🇩🇪 독일"
            )


def render_history() -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


def fetch_ai_response(user_input: str) -> str:
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1][-10:]
    ]
    try:
        resp = httpx.post(
            f"{API_BASE_URL}/chat/",
            json={
                "message": user_input,
                "session_id": st.session_state.session_id,
                "history": history,
            },
            timeout=90.0,
        )
        resp.raise_for_status()
        return resp.json()["response"]
    except httpx.ConnectError:
        logger.warning("API connection error", exc_info=True)
        return (
            "⚠️ API 서버에 연결할 수 없습니다.\n\n"
            "서버가 실행 중인지 확인해 주세요:\n"
            "```\ndocker compose up\n```\n"
            "또는 로컬 실행: `uvicorn main:app --reload` (api/ 디렉토리)"
        )
    except httpx.TimeoutException:
        logger.warning("API request timeout", exc_info=True)
        return "⚠️ 응답 시간이 초과되었습니다. 다시 시도해 주세요."
    except Exception:
        logger.exception("Unhandled error while calling API")
        return "⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

st.set_page_config(
    page_title="VisaGuide AI",
    page_icon="🛂",
    layout="centered",
    initial_sidebar_state="expanded",
)

load_styles()

init_session_state()
example_queries = load_example_queries()

# ── 사이드바 ─────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar(example_queries)

# ── 메인 영역 ────────────────────────────────────────────────────────────
render_header()

# ── 초기 인사 ────────────────────────────────────────────────────────────
render_initial_greeting()

# ── 대화 히스토리 출력 ────────────────────────────────────────────────────
render_history()

# ── 사이드바 예시 버튼 처리 ──────────────────────────────────────────────
pending = st.session_state.pop("pending_input", None)

# ── 채팅 입력 ────────────────────────────────────────────────────────────
user_input = st.chat_input("질문을 입력하세요 (예: 캐나다 취업 비자 알고 싶어요)") or pending

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("비자 정보를 검색 중입니다..."):
            ai_response = fetch_ai_response(user_input)

        st.markdown(ai_response)

    st.session_state.messages.append({"role": "assistant", "content": ai_response})
