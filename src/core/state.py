"""
State definitions for LangGraph multi-agent system.
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from operator import add


class AgentState(TypedDict):
    """
    State for the multi-agent system.
    This state is passed between nodes in the LangGraph.
    """

    # User input
    question: str
    conversation_history: List[Dict[str, str]]
    session_id: str

    # Planning and orchestration
    plan: Optional[Dict[str, Any]]
    current_step: int
    max_iterations: int
    iteration_count: int

    # Agent execution tracking
    execution_log: Annotated[List[Dict[str, Any]], add]  # Append-only
    agent_results: Dict[str, Any]

    # Intermediate results
    table_metadata: Optional[List[Dict[str, Any]]]
    rag_context: Optional[List[Dict[str, Any]]]
    genie_result: Optional[Dict[str, Any]]

    # Cache tracking
    cache_hits: int
    cache_misses: int

    # Human-in-loop
    needs_clarification: bool
    clarification_question: Optional[str]
    user_clarification: Optional[str]

    # Final output
    final_answer: Optional[str]
    synthesis_result: Optional[Dict[str, Any]]

    # Error handling and feedback
    errors: Annotated[List[str], add]  # Append-only
    should_replan: bool
    replan_reason: Optional[str]

    # Status
    is_complete: bool
    success: bool

    # Metadata
    start_time: float
    end_time: Optional[float]


def create_initial_state(
    question: str,
    session_id: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> AgentState:
    """
    Create initial state for a new query.

    Args:
        question: User question
        session_id: Session identifier
        conversation_history: Previous conversation

    Returns:
        Initial AgentState
    """
    import time

    return {
        "question": question,
        "conversation_history": conversation_history or [],
        "session_id": session_id,
        "plan": None,
        "current_step": 0,
        "max_iterations": 10,
        "iteration_count": 0,
        "execution_log": [],
        "agent_results": {},
        "table_metadata": None,
        "rag_context": None,
        "genie_result": None,
        "cache_hits": 0,
        "cache_misses": 0,
        "needs_clarification": False,
        "clarification_question": None,
        "user_clarification": None,
        "final_answer": None,
        "synthesis_result": None,
        "errors": [],
        "should_replan": False,
        "replan_reason": None,
        "is_complete": False,
        "success": False,
        "start_time": time.time(),
        "end_time": None,
    }
