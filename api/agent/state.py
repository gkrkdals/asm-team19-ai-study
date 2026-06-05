from typing import TypedDict, List, Optional, Annotated
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    country: Optional[str]           # US, JP, GB, CA, AU, DE
    purpose: Optional[str]           # employment, study, travel, long_stay, working_holiday
    duration: Optional[str]
    profession: Optional[str]
    has_sponsor: Optional[bool]
    is_exception: bool
    exception_type: Optional[str]    # extension, status_change, rejection
    is_visa_related: bool            # 비자 도메인 질문 여부(아니면 general_chat)
    is_followup: bool                # 기존 비자에 대한 후속/상세 질문(신규 추천 아님) → 라이트 표시
    search_results: Optional[str]    # 라우팅 기준 컨텍스트(비자 RAG → 웹검색)
    extra_context: Optional[str]     # 교차 예외규칙 등 보조 컨텍스트(항상 프롬프트에 병합)
    web_query: Optional[str]         # (재생성된) 웹 검색어
    search_attempts: int             # 웹 검색 재시도 횟수
    search_quality: Optional[str]    # good | poor (신뢰도 게이트 결과)
    kb_written: Optional[str]        # 학습 저장된 문서 ID(고신뢰 웹검색 결과 → ChromaDB)
    deep_search: bool                # 공식 사이트 '상세 탐색'(Tavily advanced + 원문) 요청 여부
    final_response: Optional[str]
    # 워크플로우 트레이스용 진단 로그. 각 노드가 자신이 참조한 입력(질의어 등)과
    # 산출물(결과 수 등)을 1건씩 append 한다(누적). 화면 표기/디버깅 전용이며
    # 비즈니스 로직에는 영향을 주지 않는다.
    node_details: Annotated[List[dict], operator.add]
