"""
백엔드 워크플로우 실시간 트레이스 라우터(순수 JSON/SSE API).

화면(HTML)은 별도 Express 정적 서버(web/, :3000)가 서빙하고, 브라우저가
아래 JSON/SSE 엔드포인트를 CORS 로 직접 호출한다.

제공 엔드포인트(경로는 아래 상수에서 한곳으로 관리 → URL 변경 용이)
────────────────────────────────────────────────────────────────────
  GET  {TOPOLOGY_PATH}  : LangGraph 노드/엣지 토폴로지(인트로스펙션) JSON
  POST {STREAM_PATH}    : 사용자 입력을 받아 노드 실행을 SSE 로 실시간 스트리밍
                          (호출자에게 스트리밍 + 동시에 이벤트 버스로 브로드캐스트)
  GET  {LIVE_PATH}      : 버스를 구독해 '다른 곳(고객 SPA 등)에서 발생한' 실행을
                          실시간으로 받아보는 SSE (대시보드 전용)
  POST {RUN_PATH}       : 대시보드 자체 입력 → 백그라운드로 실행 후 버스로 브로드캐스트
  GET  {SESSIONS_PATH}  : 통합 허브용 세션 개요 JSON

확장 유연성
────────────────────────────────────────────────────────────────────
- 실행 이벤트는 ``graph.astream(stream_mode="updates")`` 를 그대로 사용하므로,
  graph.py 에 노드를 추가하면 별도 수정 없이 자동으로 트레이스에 나타난다.
- 토폴로지는 컴파일된 그래프의 ``get_graph()`` 인트로스펙션 결과라 역시 자동 반영.
- 노드 한글 라벨/데이터 출처/간선 라벨은 agent/trace_meta.py 에서 보강한다.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, JSONResponse

from agent.graph import get_graph
from agent.event_bus import bus
from agent.trace_meta import (
    describe_node,
    summarize_update,
    redact_update,
    extract_detail,
    edge_label,
    SOURCE_LABELS,
)
from routers.chat import ChatRequest, build_initial_state
import sessions_store as store

# ── 경로 상수(한곳에서 관리) ──────────────────────────────────────────────
TOPOLOGY_PATH = "/graph/topology"
STREAM_PATH = "/chat/stream"
LIVE_PATH = "/trace/live"
RUN_PATH = "/trace/run"
DASHBOARD_PATH = "/trace"               # 통합 허브(모든 세션)
SESSIONS_PATH = "/trace/sessions"       # 허브용 세션 개요 JSON

router = APIRouter(tags=["workflow"])

# 백그라운드 실행 태스크가 GC 되지 않도록 참조 유지
_bg_tasks: set[asyncio.Task] = set()

# ── 세션별 실행 중 잠금: 동일 세션에 두 페이지가 동시 요청 시 두 번째를 거절 ──
_BUSY: set[str] = set()


# ── 토폴로지 인트로스펙션 ─────────────────────────────────────────────────
def _build_topology() -> dict:
    compiled = get_graph()
    drawable = compiled.get_graph()

    nodes = []
    for node_id in drawable.nodes:
        meta = describe_node(node_id)
        kind = "terminal" if node_id in ("__start__", "__end__") else "node"
        nodes.append({"id": node_id, "kind": kind, **meta})

    edges = []
    for e in drawable.edges:
        src = getattr(e, "source", None)
        tgt = getattr(e, "target", None)
        edges.append(
            {
                "source": src,
                "target": tgt,
                "conditional": bool(getattr(e, "conditional", False)),
                "label": edge_label(src, tgt),
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "source_labels": SOURCE_LABELS,
        "paths": {
            "topology": TOPOLOGY_PATH,
            "stream": STREAM_PATH,
            "live": LIVE_PATH,
            "run": RUN_PATH,
            "dashboard": DASHBOARD_PATH,
        },
    }


@router.get(TOPOLOGY_PATH)
def topology() -> JSONResponse:
    return JSONResponse(_build_topology(), headers={"Cache-Control": "no-store"})


# ── 이벤트 생성기(스트리밍/브로드캐스트 공통 단일 소스) ─────────────────────
def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def _iter_events(req: ChatRequest):
    """그래프를 실행하며 트레이스 이벤트 dict 를 순차적으로 생성한다.

    모든 이벤트에 ``session_id`` 를 실어, 세션별 상세 트레이스/통합 허브가
    필터링·그룹화할 수 있게 한다(병렬 실행 지원).
    """
    graph = get_graph()
    state = build_initial_state(req.message, req.history, req.slots)
    run_id = uuid.uuid4().hex[:8]
    sid = req.session_id or "default"

    # 동일 세션 동시 요청 방지: 이미 실행 중이면 즉시 거절
    if sid in _BUSY:
        yield {
            "type": "error", "run_id": run_id, "session_id": sid,
            "code": "BUSY",
            "message": "이 세션은 현재 다른 탭에서 답변 중입니다. 잠시 후 다시 시도해 주세요.",
        }
        return

    _BUSY.add(sid)
    try:
        title = store.session_title(sid)
    except Exception:  # noqa: BLE001
        title = sid

    topo = _build_topology()
    t0 = time.perf_counter()
    last = t0

    yield {
        "type": "start",
        "run_id": run_id,
        "session_id": sid,
        "session_title": title,
        "message": req.message,
        "ts": time.time(),                 # 정렬키(허브: 라이브·영속 공통 epoch float)
        "nodes": topo["nodes"],
        "edges": topo["edges"],
        "source_labels": topo["source_labels"],
    }

    final_response = None
    streamed_tokens = ""
    step = 0
    is_visa = None                          # intent_classifier 가 내는 is_visa_related 캡처(done 에 실어 카드 분기)
    is_followup = False                     # 기존 비자 후속/상세 질문 여부(라이트 카드 분기)
    slots = {"country": None, "purpose": None, "duration": None, "profession": None, "exception_type": None}
    try:
        # 멀티모드 스트리밍:
        #  - "updates" : 노드 종료 시 State 델타(노드 이벤트)
        #  - "messages": 노드 내부 LLM 토큰(최종 답변만 골라 token 이벤트로 방출)
        async for mode, payload in graph.astream(
            state, stream_mode=["updates", "messages"]
        ):
            if mode == "messages":
                msg_chunk, meta = payload
                # 최종 답변 노드(response_formatter/general_chat)의 토큰만 스트리밍한다.
                if meta.get("langgraph_node") in ("response_formatter", "general_chat"):
                    text = getattr(msg_chunk, "content", "") or ""
                    if text:
                        streamed_tokens += text
                        yield {
                            "type": "token",
                            "run_id": run_id,
                            "session_id": sid,
                            "node": "response_formatter",
                            "text": text,
                        }
                continue

            # mode == "updates"
            now = time.perf_counter()
            for node, update in payload.items():
                step += 1
                if update and update.get("final_response"):
                    final_response = update["final_response"]
                if update and "is_visa_related" in update:
                    is_visa = update["is_visa_related"]
                    is_followup = bool(update.get("is_followup"))
                    # 의도분류 직후 조기 신호 → 프론트가 답변 토큰을 그리기 전에
                    # 카드/평문/라이트를 결정(깜빡임 방지)
                    yield {
                        "type": "meta",
                        "run_id": run_id,
                        "session_id": sid,
                        "is_visa_related": is_visa,
                        "is_followup": is_followup,
                    }
                if update:
                    changed = False
                    for _k in ("country", "purpose", "duration", "profession", "exception_type"):
                        v = update.get(_k)
                        if v and v != slots[_k]:
                            slots[_k] = v
                            changed = True
                    if changed:
                        # 슬롯이 확정되는 즉시 조기 방출 → 프론트가 요약 카드를 답변보다 먼저 렌더(이슈 #12)
                        yield {
                            "type": "slots",
                            "run_id": run_id,
                            "session_id": sid,
                            "slots": dict(slots),
                        }
                meta = describe_node(node)
                yield {
                    "type": "node",
                    "run_id": run_id,
                    "session_id": sid,
                    "step": step,
                    "node": node,
                    "label": meta["label"],
                    "icon": meta["icon"],
                    "desc": meta["desc"],
                    "sources": meta["sources"],
                    "source_labels": meta["source_labels"],
                    "produces": meta["produces"],
                    "summary": summarize_update(node, update),
                    "detail": extract_detail(update),
                    "update": redact_update(update),
                    "elapsed_ms": round((now - last) * 1000),
                    "total_ms": round((now - t0) * 1000),
                }
            last = now
    except Exception as e:  # noqa: BLE001
        yield {"type": "error", "run_id": run_id, "session_id": sid, "message": str(e)}
    finally:
        _BUSY.discard(sid)   # 완료·오류·취소 어떤 경우든 잠금 해제

    # 토큰 스트림이 있었으면 그것을 최종 답변으로 사용(updates 누락 대비)
    if not final_response and streamed_tokens:
        final_response = streamed_tokens

    yield {
        "type": "done",
        "run_id": run_id,
        "session_id": sid,
        "final_response": final_response,
        "slots": slots,
        "is_visa_related": is_visa,         # 프론트: 추천(비자) 답변일 때만 VISA GUIDANCE 카드
        "is_followup": is_followup,         # 기존 비자 후속/상세 → 라이트 카드(분류표·표지 생략)
        "total_ms": round((time.perf_counter() - t0) * 1000),
    }


# ── POST /chat/stream : 호출자에게 스트리밍 + 버스 브로드캐스트 ─────────────
@router.post(STREAM_PATH)
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    async def gen():
        async for evt in _iter_events(req):
            await bus.publish(evt)          # 대시보드(/trace/live)로도 전달
            yield _sse(evt)                 # 호출자(고객 SPA/CLI)에게 스트리밍
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── POST /trace/run : 대시보드 자체 입력 → 백그라운드 실행 후 브로드캐스트 ───
@router.post(RUN_PATH)
async def trace_run(req: ChatRequest) -> JSONResponse:
    async def _bg():
        async for evt in _iter_events(req):
            await bus.publish(evt)

    task = asyncio.create_task(_bg())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return JSONResponse({"status": "started"})


# ── GET /trace/live : 버스 구독 SSE ───────────────────────────────────────
#    session_id 가 주어지면 해당 세션만(상세 트레이스), 없으면 전체(통합 허브).
@router.get(LIVE_PATH)
async def trace_live(session_id: str | None = Query(default=None)) -> StreamingResponse:
    async def gen():
        q = bus.subscribe(session_id=session_id)
        try:
            yield _sse({"type": "connected", "session_id": session_id})
            # 직전/진행 중 실행이 있으면 먼저 리플레이 → 늦게 열어도 즉시 그려진다.
            for evt in bus.replay(session_id):
                yield _sse(evt)
            while True:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield _sse(evt)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # keepalive (EventSource 는 주석 무시)
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── GET /trace/sessions : 통합 허브용 세션 개요 JSON ───────────────────────
def _to_epoch(value) -> float:
    """ISO8601 문자열/숫자를 정렬용 epoch float 로 통일(라이브 ts 와 같은 타입)."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def _persisted_overview() -> list[dict]:
    """영속 세션(data/sessions.json)을 허브 카드 형태로 매핑.

    인메모리 버스가 비어도(재시작 직후 등) 과거 대화가 허브 목록에 보이게 한다.
    스텝 트레이스는 영속되지 않으므로 목록 표시까지만(상세 페이지 복원은 범위 밖).
    """
    out: list[dict] = []
    for summ in store.list_sessions():
        sid = summ.get("id")
        if not sid:
            continue
        full = store.get_session(sid) or {}
        msgs = full.get("messages") or []
        last_run = full.get("last_run") or {}
        # 빈 '새 대화' 스텁 제외(메시지도 없고 실행 기록도 없는 세션)
        if not msgs and not full.get("last_run"):
            continue
        first_user = next(
            (m.get("content", "") for m in msgs if m.get("role") == "user"), ""
        )
        title = full.get("title") or first_user or sid
        out.append({
            "session_id": sid,
            "title": title,
            "message": first_user or title,
            "status": "done",
            "current_node": "기록",
            "node_icon": "🗂️",
            "node_count": len(last_run.get("steps", [])),
            "total_ms": last_run.get("total_ms"),
            "run_id": "p_" + sid,
            "ts": _to_epoch(full.get("updated") or full.get("created")),
            "persisted": True,
        })
    return out


@router.get(SESSIONS_PATH)
def trace_sessions() -> JSONResponse:
    live = bus.sessions_overview()
    live_ids = {s["session_id"] for s in live}
    merged = live + [s for s in _persisted_overview() if s["session_id"] not in live_ids]
    merged.sort(key=lambda s: s.get("ts") or 0, reverse=True)
    return JSONResponse({"sessions": merged}, headers={"Cache-Control": "no-store"})
