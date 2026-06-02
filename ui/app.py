import streamlit as st
import httpx
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
# 사용자 브라우저가 직접 여는 대시보드 URL(서버 내부 주소 API_BASE_URL 과 구분).
# Docker 실행 시 docker-compose 에서 http://localhost:8000/trace 로 주입한다.
TRACE_URL = os.getenv("TRACE_URL", "http://localhost:8000/trace")
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
    st.markdown("### 🔬 백엔드 트레이스")
    last_user = next(
        (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"),
        "",
    )
    trace_link = TRACE_URL + (f"?seed={quote(last_user)}" if last_user else "")
    st.link_button(
        "워크플로우 실시간 보기 ↗",
        trace_link,
        use_container_width=True,
        help="LangGraph 노드·벡터DB·웹검색이 단계별로 데이터를 정제하는 과정을 별도 화면에서 실시간으로 봅니다.",
    )

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


def stream_workflow(user_input: str):
    """백엔드 /chat/stream(SSE)을 소비하며 노드 실행 이벤트를 차례로 yield 한다."""
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1][-10:]
    ]
    with httpx.stream(
        "POST",
        f"{API_BASE_URL}/chat/stream",
        json={
            "message": user_input,
            "session_id": st.session_state.session_id,
            "history": history,
        },
        timeout=120.0,
    ) as resp:
        resp.raise_for_status()
        buf = ""
        for chunk in resp.iter_text():
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                for line in block.split("\n"):
                    if line.startswith("data:"):
                        try:
                            yield json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            logger.warning("Bad SSE line: %s", line)


def render_workflow_and_answer(user_input: str) -> str:
    """워크플로우 단계를 실시간 표시하고, 최종 답변을 토큰 단위로 갱신(타자기 효과)한다.

    - 노드 진행 상황은 접이식 status 에, 답변은 그 아래 placeholder 에 스트리밍한다.
    - 스트리밍 실패/토큰 미수신 시 done 의 전체 답변 또는 비스트리밍 /chat/ 로 폴백한다.
    """
    status = st.status("🔬 백엔드 워크플로우 실행 중…", expanded=True)
    answer_ph = st.empty()
    acc = ""
    final_response = None
    try:
        for evt in stream_workflow(user_input):
            etype = evt.get("type")
            if etype == "node":
                srcs = " · ".join(evt.get("source_labels", []))
                lines = " / ".join((evt.get("summary") or {}).get("lines", []))
                status.markdown(
                    f"**{evt.get('step')}. {evt.get('icon','')} {evt.get('label')}**"
                    f"  ·  ⏱ {evt.get('elapsed_ms')}ms"
                )
                status.caption(f"📥 참조: {srcs or '—'}  ·  🧪 {lines}")
            elif etype == "token":
                acc += evt.get("text", "")
                answer_ph.markdown(acc + " ▌")   # 커서로 스트리밍 표현
            elif etype == "done":
                final_response = evt.get("final_response") or acc
                status.update(
                    label=f"✅ 워크플로우 완료 (총 {evt.get('total_ms')}ms)",
                    state="complete",
                )
            elif etype == "error":
                status.update(label=f"⚠️ 백엔드 오류: {evt.get('message')}", state="error")
    except httpx.ConnectError:
        logger.warning("Stream connection error", exc_info=True)
        final_response = fetch_ai_response(user_input)
    except Exception:
        logger.exception("Streaming failed, falling back to /chat/")

    final = final_response or acc or fetch_ai_response(user_input)
    answer_ph.markdown(final)   # 커서 제거 + 마크다운 최종본
    return final


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
        # 답변은 render_workflow_and_answer 내부 placeholder 가 직접 렌더(토큰 스트리밍)
        ai_response = render_workflow_and_answer(user_input)

    st.session_state.messages.append({"role": "assistant", "content": ai_response})
