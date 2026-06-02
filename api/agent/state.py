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
    search_results: Optional[str]
    final_response: Optional[str]
    # 워크플로우 트레이스용 진단 로그. 각 노드가 자신이 참조한 입력(질의어 등)과
    # 산출물(결과 수 등)을 1건씩 append 한다(누적). 화면 표기/디버깅 전용이며
    # 비즈니스 로직에는 영향을 주지 않는다.
    node_details: Annotated[List[dict], operator.add]
