"""
백엔드 워크플로우 실시간 트레이스 라우터.

제공 엔드포인트(경로는 아래 상수에서 한곳으로 관리 → URL 변경 용이)
────────────────────────────────────────────────────────────────────
  GET  {TOPOLOGY_PATH}  : LangGraph 노드/엣지 토폴로지(인트로스펙션) JSON
  POST {STREAM_PATH}    : 사용자 입력을 받아 노드 실행을 SSE 로 실시간 스트리밍
                          (호출자에게 스트리밍 + 동시에 이벤트 버스로 브로드캐스트)
  GET  {LIVE_PATH}      : 버스를 구독해 '다른 곳(고객 SPA 등)에서 발생한' 실행을
                          실시간으로 받아보는 SSE (대시보드 전용)
  POST {RUN_PATH}       : 대시보드 자체 입력 → 백그라운드로 실행 후 버스로 브로드캐스트
  GET  {DASHBOARD_PATH} : 위 엔드포인트들을 소비하는 라이브 대시보드 HTML

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
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse

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

_STATIC = Path(__file__).resolve().parent.parent / "static"
_DASHBOARD_HTML = _STATIC / "trace.html"        # 세션별 상세 트레이스
_HUB_HTML = _STATIC / "trace_hub.html"          # 통합 병렬 허브
_APP_HTML = _STATIC / "app.html"                # 고객용 메인 SPA(하네스 디자인 100% 일치)

# 백그라운드 실행 태스크가 GC 되지 않도록 참조 유지
_bg_tasks: set[asyncio.Task] = set()


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
    state = build_initial_state(req.message, req.history)
    run_id = uuid.uuid4().hex[:8]
    sid = req.session_id or "default"
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
        "nodes": topo["nodes"],
        "edges": topo["edges"],
        "source_labels": topo["source_labels"],
    }

    final_response = None
    streamed_tokens = ""
    step = 0
    slots = {"country": None, "purpose": None, "duration": None, "profession": None}
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
                if update:
                    changed = False
                    for _k in ("country", "purpose", "duration", "profession"):
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

    # 토큰 스트림이 있었으면 그것을 최종 답변으로 사용(updates 누락 대비)
    if not final_response and streamed_tokens:
        final_response = streamed_tokens

    yield {
        "type": "done",
        "run_id": run_id,
        "session_id": sid,
        "final_response": final_response,
        "slots": slots,
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
@router.get(SESSIONS_PATH)
def trace_sessions() -> JSONResponse:
    return JSONResponse({"sessions": bus.sessions_overview()},
                        headers={"Cache-Control": "no-store"})


def _read_html(path: Path) -> HTMLResponse:
    try:
        html = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return HTMLResponse(f"<h1>{path.name} 을 찾을 수 없습니다.</h1>", status_code=500)
    # 브라우저가 옛 대시보드를 캐시하지 않도록(실시간 연동 보장)
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


# ── GET / : 고객용 메인 SPA(하네스 프로토타입 디자인, 백엔드 동일 출처) ──────
@router.get("/", response_class=HTMLResponse)
def app_spa() -> HTMLResponse:
    return _read_html(_APP_HTML)


# ── GET /trace : 통합 병렬 허브(모든 세션을 간단 카드 + 상세 링크로) ────────
@router.get(DASHBOARD_PATH, response_class=HTMLResponse)
def hub() -> HTMLResponse:
    return _read_html(_HUB_HTML)


# ── GET /{session_id}/trace : 세션별 상세 트레이스(개별 워크플로우) ──────────
@router.get("/{session_id}/trace", response_class=HTMLResponse)
def session_dashboard(session_id: str) -> HTMLResponse:
    return _read_html(_DASHBOARD_HTML)
