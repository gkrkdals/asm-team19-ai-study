"""
대화 세션 영속 스토어(파일 기반).

브라우저 새로고침/서버 재시작에도 대화가 보존되도록, 세션(대화)을 백엔드에서
소유하고 JSON 파일(data/sessions.json)에 저장한다. RESTful 라우터(routers/sessions.py)
와 워크플로우 트레이스가 이 스토어를 단일 출처로 사용한다.

세션 스키마
────────────────────────────────────────────────────────────────────
{
  "id":          str,
  "title":       str,
  "description": str,            # 한줄 설명
  "tags":        list[str],      # 예: ["장기체류","취업"]
  "created":     ISO8601,
  "updated":     ISO8601,
  "messages":    [{"role","content","ts", "is_visa"?:bool, "slots"?:dict}],  # is_visa/slots 는 비자 답변 표시 복원용(선택)
  "last_run":    {"steps":[...], "total_ms":int, "followups":[...], "slots":{...}|None} | None   # 우측 패널/트레이스·요약 카드 복원용
}

주의: 단일 uvicorn 워커(인메모리 + 파일) 기준의 prototype. 멀티 워커/수평 확장
시에는 외부 DB(SQLite/Redis 등)로 교체해야 한다.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime

_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
_STORE_PATH = os.path.join(_DATA_DIR, "sessions.json")

# 추천 태그(프론트 멀티셀렉트와 공유). 자유 태그도 허용.
SUGGESTED_TAGS = ["장기체류", "취업", "유학", "여행", "워킹홀리데이", "예외상황", "기타"]

_lock = threading.RLock()
_sessions: dict[str, dict] = {}
_loaded = False


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load() -> None:
    global _sessions, _loaded
    if _loaded:
        return
    try:
        with open(_STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _sessions = data
    except FileNotFoundError:
        _sessions = {}
    except Exception:
        _sessions = {}
    _loaded = True


def _persist() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = _STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_sessions, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _STORE_PATH)


def _summary(s: dict) -> dict:
    """목록용 요약(메시지 본문 제외)."""
    return {
        "id": s["id"],
        "title": s.get("title") or "새 대화",
        "description": s.get("description", ""),
        "tags": s.get("tags", []),
        "pinned": bool(s.get("pinned", False)),
        "created": s.get("created", ""),
        "updated": s.get("updated", ""),
        "message_count": len(s.get("messages", [])),
        "has_run": bool(s.get("last_run")),
    }


# ── 공개 API ──────────────────────────────────────────────────────────────
def list_sessions() -> list[dict]:
    """목록 정렬: 고정(pinned) 우선, 그 안에서 생성 시각(created) 내림차순."""
    with _lock:
        _load()
        items = sorted(
            _sessions.values(),
            key=lambda s: (bool(s.get("pinned", False)), s.get("created", "")),
            reverse=True,
        )
        return [_summary(s) for s in items]


def get_session(sid: str) -> dict | None:
    with _lock:
        _load()
        s = _sessions.get(sid)
        return json.loads(json.dumps(s)) if s else None


def create_session(title: str = "새 대화", session_id: str | None = None) -> dict:
    with _lock:
        _load()
        sid = session_id or ("s_" + uuid.uuid4().hex[:12])
        now = _now()
        _sessions[sid] = {
            "id": sid,
            "title": title or "새 대화",
            "description": "",
            "tags": [],
            "pinned": False,
            "created": now,
            "updated": now,
            "messages": [],
            "last_run": None,
        }
        _persist()
        return json.loads(json.dumps(_sessions[sid]))


def update_session(sid: str, *, title=None, description=None, tags=None, pinned=None) -> dict | None:
    with _lock:
        _load()
        s = _sessions.get(sid)
        if not s:
            return None
        if title is not None:
            s["title"] = title.strip()[:60] or "새 대화"
        if description is not None:
            s["description"] = description.strip()[:160]
        if tags is not None:
            s["tags"] = [t.strip()[:20] for t in tags if t and t.strip()][:8]
        if pinned is not None:
            s["pinned"] = bool(pinned)
        # 고정 토글만 한 경우에는 updated(최근활동)를 갱신하지 않는다.
        if not (pinned is not None and title is None and description is None and tags is None):
            s["updated"] = _now()
        _persist()
        return json.loads(json.dumps(s))


def delete_session(sid: str) -> bool:
    with _lock:
        _load()
        existed = _sessions.pop(sid, None) is not None
        if existed:
            _persist()
        return existed


def append_message(sid: str, role: str, content: str, *, auto_title: bool = True,
                   is_visa: bool | None = None, slots: dict | None = None,
                   is_followup: bool | None = None) -> dict | None:
    """세션에 메시지를 추가한다. 세션이 없으면 생성한다.

    is_visa/slots 는 비자 추천 답변(assistant)의 표시 복원용 선택 메타 — 주어질 때만 저장한다.
    """
    with _lock:
        _load()
        s = _sessions.get(sid)
        if not s:
            s = create_session(session_id=sid)
            _load()
            s = _sessions.get(sid)
        msg = {"role": role, "content": content, "ts": _now()}
        if is_visa is not None:
            msg["is_visa"] = is_visa
        if slots:
            msg["slots"] = slots
        if is_followup is not None:
            msg["is_followup"] = is_followup
        s["messages"].append(msg)
        # 첫 사용자 메시지로 제목 자동 설정
        if auto_title and role == "user" and (not s.get("title") or s["title"] == "새 대화"):
            s["title"] = content.strip()[:30] or "새 대화"
        s["updated"] = _now()
        _persist()
        return json.loads(json.dumps(s))


def set_last_run(sid: str, run: dict) -> None:
    with _lock:
        _load()
        s = _sessions.get(sid)
        if not s:
            return
        s["last_run"] = run
        s["updated"] = _now()
        _persist()


def session_title(sid: str) -> str:
    with _lock:
        _load()
        s = _sessions.get(sid)
        return (s.get("title") if s else "") or sid
