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
