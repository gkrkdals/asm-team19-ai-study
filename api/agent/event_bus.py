"""
프로세스 내 인메모리 이벤트 버스(pub/sub) — 세션별 트레이스 지원.

용도
────────────────────────────────────────────────────────────────────
고객 SPA(:8000/)에서 발생한 채팅 실행을 트레이스 대시보드(:8000/trace)가 실시간으로
받아 보여준다. 여러 대화 세션이 동시에 실행될 수 있으므로(병렬 처리), 이벤트마다
``session_id`` 를 실어 보내고:

  - 세션별 상세 트레이스: GET /{sid}/trace  ← /trace/live?session_id=<sid> (필터 구독)
  - 통합 허브:           GET /trace          ← /trace/live (전체 구독, 세션별 그룹)

구독자는 ``subscribe(session_id=...)`` 로 특정 세션만, ``subscribe()`` 로 전체를
받는다. 각 세션의 직전/진행 중 실행은 ``replay(session_id)`` 로 리플레이한다.

주의: 단일 uvicorn 워커 기준(인메모리). 멀티 워커/수평 확장 시 Redis Pub/Sub 등
외부 브로커로 교체해야 한다(prototype 한정).
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

_NO_SESSION = "_default"


class EventBus:
    def __init__(self) -> None:
        # 구독 큐 → 필터(session_id|None). None 이면 모든 세션 수신(허브).
        self._subscribers: dict[asyncio.Queue, str | None] = {}
        # 세션별 '가장 최근 실행 한 건'의 이벤트열(start→…→done) 리플레이 버퍼.
        self._last_runs: dict[str, list[dict]] = {}

    # ── 구독 ────────────────────────────────────────────────────────────
    def subscribe(self, session_id: str | None = None) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=4000)
        self._subscribers[q] = session_id
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.pop(q, None)

    # ── 리플레이/조회 ────────────────────────────────────────────────────
    def replay(self, session_id: str | None = None) -> list[dict]:
        """세션의 직전/진행 중 이벤트열. session_id=None 이면 모든 세션을 합쳐 반환."""
        if session_id is not None:
            return list(self._last_runs.get(session_id, []))
        merged: list[dict] = []
        for evts in self._last_runs.values():
            merged.extend(evts)
        return merged

    def sessions_overview(self) -> list[dict]:
        """허브용: 세션별 최신 실행 요약(제목·현재 노드·상태·경과)."""
        out = []
        for sid, evts in self._last_runs.items():
            if not evts:
                continue
            start = next((e for e in evts if e.get("type") == "start"), {})
            done = next((e for e in reversed(evts) if e.get("type") == "done"), None)
            last_node = next((e for e in reversed(evts) if e.get("type") == "node"), {})
            nodes = [e for e in evts if e.get("type") == "node"]
            out.append({
                "session_id": sid,
                "title": start.get("session_title") or start.get("message", "")[:30] or sid,
                "message": start.get("message", ""),
                "status": "done" if done else "running",
                "current_node": last_node.get("label", ""),
                "node_icon": last_node.get("icon", ""),
                "node_count": len(nodes),
                "total_ms": (done or {}).get("total_ms"),
                "run_id": start.get("run_id"),
                "ts": start.get("ts"),
            })
        # 최근 실행 먼저
        out.sort(key=lambda x: x.get("ts") or 0, reverse=True)
        return out

    # ── 발행 ────────────────────────────────────────────────────────────
    def _record(self, event: dict) -> None:
        sid = event.get("session_id") or _NO_SESSION
        etype = event.get("type")
        if etype == "start":
            self._last_runs[sid] = [event]
        elif etype in ("node", "token", "done", "error"):
            buf = self._last_runs.setdefault(sid, [])
            if len(buf) < 6000:     # 토큰이 많을 수 있어 상한
                buf.append(event)

    async def publish(self, event: dict) -> None:
        """필터에 맞는 구독자에게 이벤트를 보낸다. 큐가 가득 차면 건너뛴다."""
        self._record(event)
        sid = event.get("session_id")
        for q, flt in list(self._subscribers.items()):
            if flt is not None and flt != sid:
                continue   # 이 구독자는 다른 세션만 관심
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("EventBus subscriber queue full — dropping event")

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# 전역 싱글턴
bus = EventBus()
