"""
프로세스 내 인메모리 이벤트 버스(pub/sub).

용도
────────────────────────────────────────────────────────────────────
Streamlit(:8501)에서 발생한 채팅 실행을 트레이스 대시보드(:8000/trace)가
실시간으로 받아 보여주기 위한 브로드캐스트 채널이다. FastAPI 단일 프로세스
안에서 동작한다:

    Streamlit ──POST /chat/stream──▶ API 프로세스(graph 실행)
                                         │  매 노드 이벤트 publish()
                                         ▼
    대시보드 ◀──GET /trace/live(SSE)── subscribe() 한 구독자 큐

주의: 단일 uvicorn 워커 기준. 멀티 워커/수평 확장 시에는 Redis Pub/Sub 등
외부 브로커로 교체해야 한다(prototype 한정).
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        # 가장 최근 실행 한 건의 이벤트열(start→…→done)을 보관한다.
        # 대시보드를 '실행 도중/직후'에 열어도 즉시 같은 실행을 그릴 수 있도록 리플레이용.
        self._last_run: list[dict] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _record(self, event: dict) -> None:
        etype = event.get("type")
        if etype == "start":
            self._last_run = [event]
        elif etype in ("node", "token", "done", "error"):
            # 과도한 메모리 사용 방지(토큰이 많을 수 있음)
            if len(self._last_run) < 5000:
                self._last_run.append(event)

    def replay(self) -> list[dict]:
        """직전/진행 중 실행의 이벤트열 스냅샷을 돌려준다(없으면 빈 리스트)."""
        return list(self._last_run)

    async def publish(self, event: dict) -> None:
        """모든 구독자에게 이벤트를 보낸다. 큐가 가득 차면 해당 구독자는 건너뛴다."""
        self._record(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("EventBus subscriber queue full — dropping event")

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# 전역 싱글턴
bus = EventBus()
