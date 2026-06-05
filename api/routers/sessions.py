"""
대화 세션 RESTful 라우터.

새로고침/재시작에도 대화를 보존하고, 세션별 메타데이터(이름·한줄설명·태그)를
관리한다. 프론트엔드(고객 SPA, web/public/app.html)는 이 API 를 단일 출처로 사용한다.

엔드포인트
────────────────────────────────────────────────────────────────────
  GET    /sessions                  세션 목록(요약)
  POST   /sessions                  세션 생성
  GET    /sessions/{sid}            세션 전체(메시지 포함)
  PATCH  /sessions/{sid}            메타데이터 수정(title/description/tags)
  DELETE /sessions/{sid}            세션 삭제
  POST   /sessions/{sid}/messages   메시지 추가({role, content})
  PUT    /sessions/{sid}/last_run   최근 실행(워크플로우 단계) 저장
  GET    /sessions/meta/tags        추천 태그 목록
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import sessions_store as store

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateReq(BaseModel):
    title: Optional[str] = "새 대화"
    session_id: Optional[str] = None


class PatchReq(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    pinned: Optional[bool] = None   # 상단 고정 토글


class MessageReq(BaseModel):
    role: str
    content: str
    is_visa: Optional[bool] = None   # 비자 추천 답변 여부(일반대화=False) — 새로고침 후 카드/평문 복원
    slots: Optional[dict] = None     # 답변 시점 파싱 슬롯 — 새로고침 후 요약 카드·동적 제목 복원
    is_followup: Optional[bool] = None  # 후속/상세 질문 답변 여부 — 새로고침 후 라이트 카드 복원


class LastRunReq(BaseModel):
    steps: list = []
    total_ms: Optional[int] = None
    followups: Optional[List[str]] = None   # AI 동적 생성 후속 질문 칩(새로고침 보존)
    slots: Optional[dict] = None   # 파싱 슬롯(country/purpose/duration/profession) — 요약 카드 복원용


@router.get("")
@router.get("/")
def list_sessions():
    return {"sessions": store.list_sessions()}


@router.get("/meta/tags")
def suggested_tags():
    return {"tags": store.SUGGESTED_TAGS}


@router.post("")
@router.post("/")
def create_session(req: CreateReq):
    return store.create_session(title=req.title or "새 대화", session_id=req.session_id)


@router.get("/{sid}")
def get_session(sid: str):
    s = store.get_session(sid)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return s


@router.patch("/{sid}")
def patch_session(sid: str, req: PatchReq):
    s = store.update_session(
        sid, title=req.title, description=req.description, tags=req.tags, pinned=req.pinned
    )
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return s


@router.delete("/{sid}")
def delete_session(sid: str):
    ok = store.delete_session(sid)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return {"deleted": sid}


@router.post("/{sid}/messages")
def add_message(sid: str, req: MessageReq):
    s = store.append_message(sid, req.role, req.content, is_visa=req.is_visa, slots=req.slots, is_followup=req.is_followup)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return {"id": sid, "message_count": len(s["messages"]), "title": s["title"]}


@router.put("/{sid}/last_run")
def put_last_run(sid: str, req: LastRunReq):
    run = {"steps": req.steps, "total_ms": req.total_ms, "followups": req.followups or [], "slots": req.slots}
    store.set_last_run(sid, run)
    return {"id": sid, "saved": True}
