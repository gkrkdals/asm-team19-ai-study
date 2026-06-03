import streamlit as st
import httpx
import os
import json
import logging
from html import escape
from pathlib import Path
from urllib.parse import quote

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
# 사용자 브라우저가 직접 여는 트레이스 오리진(서버 내부 주소 API_BASE_URL 과 구분).
TRACE_ORIGIN = os.getenv("TRACE_ORIGIN", "http://localhost:8000")
SESSIONS_API = f"{API_BASE_URL}/sessions"
EXAMPLE_QUERIES_PATH = Path(__file__).with_name("example_queries.json")
STYLES_PATH = Path(__file__).with_name("styles.css")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("visaguide.ui")

# AI 제안이 없을 때의 후속 질문 폴백. (버튼라벨, 실제 전송 메시지)
FALLBACK_FOLLOWUPS = [
    ("🔎 더 구체적으로", "방금 안내한 비자에 대해 자격 요건·필요 서류·신청 절차를 더 구체적으로 알려줘"),
    ("🆕 최신 정보로 확인", "공식 사이트의 최신 정보로 확인해서 요건과 수수료를 알려줘"),
    ("🗂️ 다른 비자 종류는?", "같은 국가에서 신청할 수 있는 다른 비자 종류도 있는지 비교해서 알려줘"),
]
# 항상 노출하는 고정 유틸 칩(공식 사이트 딥서치)
DEEP_CHIP = ("🌐 공식 사이트 상세 탐색",
             "공식 사이트를 상세 탐색해서 최신 요건·서류·수수료·처리기간을 원문 기준으로 구체적으로 알려줘")


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


# ── 백엔드 세션 REST 클라이언트(새로고침에도 보존되는 영속 스토어) ─────────
def _api(method: str, path: str, **kw):
    try:
        r = httpx.request(method, f"{SESSIONS_API}{path}", timeout=10.0, **kw)
        r.raise_for_status()
        return r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("sessions API %s %s failed: %s", method, path, e)
        return None


def api_list_sessions() -> list[dict]:
    d = _api("GET", "")
    return (d or {}).get("sessions", []) if d else []


def api_get_session(sid: str) -> dict | None:
    return _api("GET", f"/{sid}")


def api_create_session(title: str = "새 대화") -> dict | None:
    return _api("POST", "", json={"title": title})


def api_update_session(sid: str, **meta) -> dict | None:
    return _api("PATCH", f"/{sid}", json=meta)


def api_delete_session(sid: str) -> None:
    _api("DELETE", f"/{sid}")


def api_append_message(sid: str, role: str, content: str) -> None:
    _api("POST", f"/{sid}/messages", json={"role": role, "content": content})


def api_set_last_run(sid: str, run: dict) -> None:
    _api("PUT", f"/{sid}/last_run", json=run)


def api_suggested_tags() -> list[str]:
    d = _api("GET", "/meta/tags")
    return (d or {}).get("tags", []) if d else ["장기체류", "취업", "유학", "여행"]


def api_followups(history: list[dict]) -> list[str]:
    """대화 맥락 기반 AI 후속 질문 제안(백엔드 /chat/followups)."""
    try:
        r = httpx.post(f"{API_BASE_URL}/chat/followups", json={"history": history}, timeout=30.0)
        r.raise_for_status()
        return [s for s in r.json().get("suggestions", []) if s]
    except Exception as e:  # noqa: BLE001
        logger.warning("followups fetch failed: %s", e)
        return []


# ── 세션 상태(백엔드 단일 출처 + 로컬 미러) ───────────────────────────────
def _load_active(sid: str) -> None:
    """활성 세션의 메시지/메타데이터를 백엔드에서 로드해 로컬 미러에 채운다."""
    full = api_get_session(sid)
    if not full:                       # 백엔드에 없으면 생성
        full = api_create_session()
        sid = full["id"] if full else sid
    st.session_state.session_id = sid
    st.session_state.messages = [
        {"role": m["role"], "content": m["content"]} for m in (full or {}).get("messages", [])
    ]
    st.session_state.active_meta = {
        "title": (full or {}).get("title", "새 대화"),
        "description": (full or {}).get("description", ""),
        "tags": (full or {}).get("tags", []),
        "last_run": (full or {}).get("last_run"),
    }
    st.session_state.loaded_sid = sid


def init_session_state() -> None:
    if "pending_input" not in st.session_state:
        st.session_state.pending_input = None
    if "wf_open" not in st.session_state:
        st.session_state.wf_open = True

    sessions = api_list_sessions()
    if not sessions:                                  # 첫 실행 → 세션 생성
        created = api_create_session()
        sessions = api_list_sessions()
    st.session_state.sessions_list = sessions

    # URL 쿼리(?sid=)에서 활성 세션 결정 → 새로고침에도 같은 세션 유지
    sid = st.query_params.get("sid")
    valid = {s["id"] for s in sessions}
    if sid not in valid:
        sid = sessions[0]["id"] if sessions else (created or {}).get("id")
    if st.query_params.get("sid") != sid:
        st.query_params["sid"] = sid

    if st.session_state.get("loaded_sid") != sid:
        _load_active(sid)


def create_conversation() -> None:
    s = api_create_session()
    if s:
        st.query_params["sid"] = s["id"]
        st.session_state.loaded_sid = None
    st.session_state.pending_input = None


def switch_conversation(sid: str) -> None:
    st.query_params["sid"] = sid
    st.session_state.loaded_sid = None
    st.session_state.pending_input = None


def delete_conversation(sid: str) -> None:
    api_delete_session(sid)
    remaining = [s for s in api_list_sessions()]
    if remaining:
        st.query_params["sid"] = remaining[0]["id"]
    else:
        new = api_create_session()
        if new:
            st.query_params["sid"] = new["id"]
    st.session_state.loaded_sid = None


# ── 사이드바 ─────────────────────────────────────────────────────────────
def _tag_chips(tags: list[str]) -> str:
    return "".join(f'<span class="tagchip">{escape(t)}</span>' for t in (tags or [])[:4])


def render_sidebar(example_queries: list[str]) -> None:
    st.markdown("## 🛂 VisaGuide AI")

    if st.button("➕ 새 대화", use_container_width=True, type="primary"):
        create_conversation()
        st.rerun()

    st.markdown("##### 💬 대화 목록")
    active_sid = st.session_state.session_id
    for s in st.session_state.sessions_list:
        sid = s["id"]
        active = sid == active_sid
        col_a, col_b = st.columns([0.82, 0.18])
        label = (s.get("title") or "새 대화")[:24]
        help_txt = s.get("description") or "설명 없음"
        with col_a:
            if st.button(("🟢 " if active else "💬 ") + label,
                         key=f"conv_{sid}", use_container_width=True, help=help_txt):
                switch_conversation(sid)
                st.rerun()
        with col_b:
            if st.button("🗑", key=f"del_{sid}", use_container_width=True, help="이 대화 삭제"):
                delete_conversation(sid)
                st.rerun()
        if s.get("tags"):
            st.markdown(f'<div class="conv-tags">{_tag_chips(s["tags"])}</div>',
                        unsafe_allow_html=True)

    # ── 세션 설정(이름·한줄설명·태그) ─────────────────────────────────────
    meta = st.session_state.active_meta
    with st.expander("⚙️ 현재 대화 설정 (이름·설명·태그)", expanded=False):
        new_title = st.text_input("이름", value=meta.get("title", ""), key=f"ti_{active_sid}")
        new_desc = st.text_input("한줄 설명", value=meta.get("description", ""),
                                 key=f"de_{active_sid}", placeholder="예: 캐나다 Express Entry 상담")
        new_tags = st.multiselect("태그", options=api_suggested_tags(),
                                  default=meta.get("tags", []), key=f"tg_{active_sid}")
        if st.button("💾 저장", use_container_width=True, key=f"save_{active_sid}"):
            api_update_session(active_sid, title=new_title, description=new_desc, tags=new_tags)
            st.session_state.loaded_sid = None
            st.rerun()

    st.markdown("---")
    st.markdown("### 🔬 백엔드 트레이스")
    st.link_button("이 세션 상세 트레이스 ↗", f"{TRACE_ORIGIN}/{quote(active_sid)}/trace",
                   use_container_width=True,
                   help="이 대화 세션의 LangGraph 워크플로우를 실시간으로 봅니다.")
    st.link_button("🛰️ 통합 병렬 허브 ↗", f"{TRACE_ORIGIN}/trace", use_container_width=True,
                   help="모든 대화 세션의 병렬 실행을 한눈에 보고 각 세션 상세로 이동합니다.")

    st.markdown("---")
    st.markdown("### 예시 질문")
    for i, q in enumerate(example_queries):
        if st.button(q, use_container_width=True, key=f"btn_{i}"):
            st.session_state["pending_input"] = q

    st.markdown("### 지원 국가")
    st.markdown(
        "🇺🇸 미국 · 🇯🇵 일본 · 🇬🇧 영국 · 🇨🇦 캐나다 · 🇦🇺 호주 · 🇩🇪 독일\n\n"
        "그 외 국가는 웹검색으로 대응합니다."
    )
    st.markdown(
        '<div class="disclaimer-box">'
        "⚠️ 모든 비자 정보는 <b>참고용</b>이며, 실제 신청 시 해당 국가 공식 기관"
        "(대사관·이민국)에서 최신 정보를 반드시 확인하세요.</div>",
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


def render_followups() -> None:
    """답변 직후 상황별 후속 요청 칩.

    - AI 추천(🤖): /chat/followups 가 대화 맥락 기반으로 LLM 이 동적 생성.
                  세션 last_run.followups 에 저장 → 새로고침에도 보존.
    - 기본 추천(📋): AI 생성 실패 또는 세션 최초 로딩 시 정적 폴백.
    - 🌐 공식 사이트 상세 탐색: 항상 고정 노출.

    클릭 → pending_input 에 설정 → 사용자가 입력한 것처럼 자동 실행.
    """
    msgs = st.session_state.messages
    if not msgs or msgs[-1]["role"] != "assistant":
        return

    run = (st.session_state.active_meta or {}).get("last_run") or {}
    ai_followups = [s for s in (run.get("followups") or []) if s]

    if ai_followups:
        chips = [(s, s) for s in ai_followups]
        header_badge = '<span class="fu-ai">🤖 AI 추천</span>'
    else:
        chips = [(lbl, m) for lbl, m in FALLBACK_FOLLOWUPS]
        header_badge = '<span class="fu-basic">📋 기본 추천</span>'

    chips.append(DEEP_CHIP)   # 항상 노출하는 딥서치 칩

    st.markdown(
        f'<div class="followup-label">💡 이어서 물어볼까요? {header_badge}</div>',
        unsafe_allow_html=True,
    )

    # 칩을 3열 그리드로 배치
    per_row = 3
    idx = 0
    for start in range(0, len(chips), per_row):
        row = chips[start:start + per_row]
        cols = st.columns(len(row))
        for j, (label, msg) in enumerate(row):
            disp = label if len(label) <= 26 else label[:25] + "…"
            with cols[j]:
                if st.button(disp, key=f"fu_{idx}", use_container_width=True, help=label):
                    st.session_state["pending_input"] = msg
                    st.rerun()
            idx += 1


def fetch_ai_response(user_input: str) -> str:
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1][-10:]
    ]
    try:
        resp = httpx.post(
            f"{API_BASE_URL}/chat/",
            json={"message": user_input, "session_id": st.session_state.session_id,
                  "history": history},
            timeout=90.0,
        )
        resp.raise_for_status()
        return resp.json()["response"]
    except httpx.ConnectError:
        logger.warning("API connection error", exc_info=True)
        return "⚠️ API 서버에 연결할 수 없습니다. 서버 실행 여부를 확인해 주세요."
    except httpx.TimeoutException:
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
        "POST", f"{API_BASE_URL}/chat/stream",
        json={"message": user_input, "session_id": st.session_state.session_id,
              "history": history},
        timeout=180.0,
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


# ── 우측 워크플로우 패널 렌더 헬퍼 ────────────────────────────────────────
def _collect_step(evt: dict) -> dict:
    return {
        "step": evt.get("step"),
        "icon": evt.get("icon", ""),
        "label": evt.get("label", ""),
        "elapsed_ms": evt.get("elapsed_ms"),
        "srcs": " · ".join(evt.get("source_labels", [])),
        "lines": (evt.get("summary") or {}).get("lines", []),
    }


def _wf_step_html(s: dict) -> str:
    lines = "<br>".join(escape(str(x)) for x in s.get("lines", []))
    return (
        '<div class="wf-step">'
        f'<div class="wf-step-h"><span class="wf-num">{escape(str(s.get("step", "•")))}</span>'
        f'<span>{escape(s.get("icon", ""))}</span>'
        f'<span class="wf-name">{escape(s.get("label", ""))}</span>'
        f'<span class="wf-ms">{escape(str(s.get("elapsed_ms", "")))}ms</span></div>'
        f'<div class="wf-src">📥 {escape(s.get("srcs") or "—")}</div>'
        f'<div class="wf-lines">{lines}</div>'
        '</div>'
    )


def _wf_panel_header() -> None:
    st.markdown('<div class="wf-panel-title">🔬 워크플로우 트레이스</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="wf-panel-sub">LangGraph 노드가 데이터를 단계별로 정제하는 과정</div>',
        unsafe_allow_html=True,
    )


def render_workflow_panel() -> None:
    """우측 패널: 활성 대화의 '최근 실행' 워크플로우를 단계별 카드로 표시한다."""
    _wf_panel_header()
    run = (st.session_state.active_meta or {}).get("last_run")
    if run and run.get("steps"):
        cards = "".join(_wf_step_html(s) for s in run["steps"])
        st.markdown(f'<div class="wf-list">{cards}</div>', unsafe_allow_html=True)
        st.caption(f"총 {run.get('total_ms', '?')}ms · 노드 {len(run['steps'])}개 실행")
    else:
        st.markdown(
            '<div class="wf-empty">질문을 입력하면 의도분석 → 비자검색 → (필요 시)웹검색·'
            '신뢰도평가·학습저장 → 응답 생성까지 각 단계가 여기에 실시간으로 표시됩니다.</div>',
            unsafe_allow_html=True,
        )
    st.link_button("상세 실시간 트레이스 열기 ↗",
                   f"{TRACE_ORIGIN}/{quote(st.session_state.session_id)}/trace",
                   use_container_width=True)


def run_turn(user_input: str, answer_ph, wf_live) -> tuple:
    """백엔드 스트림 소비: 답변은 answer_ph 에 타자기 스트리밍, 단계는 wf_live 에 카드로 누적."""
    def wf(html: str) -> None:
        if wf_live is not None:
            wf_live.markdown(html, unsafe_allow_html=True)

    acc = ""
    final_response = None
    total_ms = None
    steps: list = []
    wf('<div class="wf-running">⏳ 워크플로우 실행 중…</div>')
    try:
        for evt in stream_workflow(user_input):
            etype = evt.get("type")
            if etype == "node":
                s = _collect_step(evt)
                steps.append(s)
                wf(_wf_step_html(s))
            elif etype == "token":
                acc += evt.get("text", "")
                answer_ph.markdown(acc + " ▌")
            elif etype == "done":
                final_response = evt.get("final_response") or acc
                total_ms = evt.get("total_ms")
                wf(f'<div class="wf-done">✅ 완료 · 총 {total_ms}ms</div>')
            elif etype == "error":
                wf(f'<div class="wf-err">⚠️ 백엔드 오류: {escape(str(evt.get("message")))}</div>')
    except httpx.ConnectError:
        logger.warning("Stream connection error", exc_info=True)
        final_response = fetch_ai_response(user_input)
    except Exception:
        logger.exception("Streaming failed, falling back to /chat/")

    final = final_response or acc or fetch_ai_response(user_input)
    answer_ph.markdown(final)
    return final, steps, total_ms


# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="VisaGuide AI", page_icon="🛂",
                   layout="wide", initial_sidebar_state="expanded")
load_styles()
init_session_state()
example_queries = load_example_queries()

with st.sidebar:
    render_sidebar(example_queries)

# ── 헤더 + 워크플로우 패널 열기/닫기 토글 ────────────────────────────────
head_l, head_r = st.columns([0.72, 0.28])
with head_l:
    render_header()
with head_r:
    toggle_label = "🔬 워크플로우 닫기 ✕" if st.session_state.wf_open else "🔬 워크플로우 열기 ☰"
    if st.button(toggle_label, use_container_width=True, key="wf_toggle",
                 help="우측 워크플로우 트레이스 패널을 사이드바처럼 열고 닫습니다 (모바일·데스크탑 공통)"):
        st.session_state.wf_open = not st.session_state.wf_open
        st.rerun()

pending = st.session_state.pop("pending_input", None)
user_input = st.chat_input("질문을 입력하세요 (예: 캐나다 취업 비자 알고 싶어요)") or pending

# ── 메인 레이아웃: 패널 열림이면 2-pane, 닫힘이면 대화 전체폭 ─────────────
if st.session_state.wf_open:
    chat_col, wf_col = st.columns([0.62, 0.38], gap="large")
else:
    chat_col, wf_col = st.container(), None

if wf_col is not None:
    with wf_col:
        if user_input:
            _wf_panel_header()
            wf_live = st.container()
        else:
            render_workflow_panel()
            wf_live = None
else:
    wf_live = None

with chat_col:
    render_initial_greeting()
    render_history()

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        api_append_message(st.session_state.session_id, "user", user_input)  # 영속화

        with st.chat_message("assistant"):
            answer_ph = st.empty()
        ai_response, steps, total_ms = run_turn(user_input, answer_ph, wf_live)

        st.session_state.messages.append({"role": "assistant", "content": ai_response})
        api_append_message(st.session_state.session_id, "assistant", ai_response)  # 영속화

        # 상황별 후속 질문 칩을 AI 로 생성(맥락 = 최근 대화) → last_run 에 저장
        hist = [{"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[-6:]]
        suggestions = api_followups(hist)
        api_set_last_run(st.session_state.session_id,
                         {"steps": steps, "total_ms": total_ms, "followups": suggestions})
        st.session_state.loaded_sid = None    # 다음 런에서 메타/제목·후속칩 갱신 반영
        st.rerun()
    else:
        render_followups()
