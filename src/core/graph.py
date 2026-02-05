"""
LangGraph StateGraph implementation for multi-agent orchestration.
This is the actual graph that coordinates all agents.
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.core.state import AgentState, create_initial_state
from src.agents.orchestrator import get_orchestrator
from src.agents.genie_agent import get_genie_agent
from src.agents.table_understanding import get_table_understanding_agent
from src.agents.rag_agent import get_rag_agent
from src.agents.synthesis_agent import get_synthesis_agent
from src.agents.human_loop import get_human_loop_agent
from src.utils.logging import get_logger, trace_function
from src.core.config import config

logger = get_logger(__name__)


class MultiAgentGraph:
    """
    LangGraph-based multi-agent system.
    Implements proper StateGraph with conditional routing.
    """

    def __init__(self):
        self.orchestrator = get_orchestrator()
        self.genie = get_genie_agent()
        self.table_agent = get_table_understanding_agent()
        self.rag_agent = get_rag_agent()
        self.synthesis = get_synthesis_agent()
        self.human_loop = get_human_loop_agent()

        # Build the graph
        self.graph = self._build_graph()

        logger.info("Initialized MultiAgentGraph with LangGraph StateGraph")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph"""

        # Create graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("table_understanding", self._table_understanding_node)
        workflow.add_node("genie", self._genie_node)
        workflow.add_node("rag", self._rag_node)
        workflow.add_node("human_input", self._human_input_node)
        workflow.add_node("synthesis", self._synthesis_node)
        workflow.add_node("replan", self._replan_node)

        # Set entry point
        workflow.set_entry_point("plan")

        # Add conditional routing
        workflow.add_conditional_edges(
            "plan",
            self._route_after_plan,
            {
                "table_understanding": "table_understanding",
                "genie": "genie",
                "rag": "rag",
                "human_input": "human_input",
                "synthesis": "synthesis",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "table_understanding",
            self._route_after_agent,
            {
                "genie": "genie",
                "rag": "rag",
                "synthesis": "synthesis",
                "replan": "replan",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "genie",
            self._route_after_agent,
            {
                "table_understanding": "table_understanding",
                "rag": "rag",
                "synthesis": "synthesis",
                "replan": "replan",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "rag",
            self._route_after_agent,
            {
                "genie": "genie",
                "synthesis": "synthesis",
                "replan": "replan",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "human_input",
            self._route_after_human,
            {
                "plan": "plan",
                "end": END,
            },
        )

        workflow.add_edge("replan", "plan")
        workflow.add_edge("synthesis", END)

        # Compile with checkpointer
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)

    # Node implementations

    @trace_function("plan_node")
    def _plan_node(self, state: AgentState) -> AgentState:
        """Planning node - creates or updates execution plan"""
        logger.info("Plan node executing")

        iteration = state["iteration_count"] + 1

        if iteration > state["max_iterations"]:
            state["is_complete"] = True
            state["success"] = False
            state["errors"].append("Max iterations reached")
            return state

        state["iteration_count"] = iteration

        # Check if we need to replan or create initial plan
        if state["plan"] is None:
            # Create initial plan
            plan = self.orchestrator._create_plan(
                state["question"],
                state["conversation_history"],
                {},
            )
            state["plan"] = plan
        else:
            # Plan already exists (from replan node)
            pass

        logger.info(f"Plan created: {len(state['plan'].get('steps', []))} steps")

        return state

    @trace_function("table_understanding_node")
    def _table_understanding_node(self, state: AgentState) -> AgentState:
        """Table understanding node"""
        logger.info("Table understanding node executing")

        try:
            # Search for relevant tables
            tables = self.table_agent.search_tables(
                state["question"],
                top_k=3,
            )

            state["table_metadata"] = tables
            state["agent_results"]["table_understanding"] = tables
            state["current_step"] += 1

        except Exception as e:
            logger.error(f"Table understanding failed: {e}")
            state["errors"].append(f"Table understanding error: {str(e)}")
            state["should_replan"] = True
            state["replan_reason"] = "Table understanding failed"

        return state

    @trace_function("genie_node")
    def _genie_node(self, state: AgentState) -> AgentState:
        """Genie query node"""
        logger.info("Genie node executing")

        try:
            result = self.genie.query(
                state["question"],
                use_cache=True,
            )

            if result.get("success"):
                state["genie_result"] = result
                state["agent_results"]["genie"] = result
                state["current_step"] += 1

                # Track cache hit
                if result.get("cached"):
                    state["cache_hits"] += 1
                else:
                    state["cache_misses"] += 1

            else:
                state["errors"].append(f"Genie query failed: {result.get('error')}")
                state["should_replan"] = True
                state["replan_reason"] = "Genie query failed"

        except Exception as e:
            logger.error(f"Genie node failed: {e}")
            state["errors"].append(f"Genie error: {str(e)}")
            state["should_replan"] = True
            state["replan_reason"] = "Genie exception"

        return state

    @trace_function("rag_node")
    def _rag_node(self, state: AgentState) -> AgentState:
        """RAG retrieval node"""
        logger.info("RAG node executing")

        try:
            contexts = self.rag_agent.retrieve_context(
                state["question"],
                top_k=5,
            )

            state["rag_context"] = contexts
            state["agent_results"]["rag"] = contexts
            state["current_step"] += 1

        except Exception as e:
            logger.error(f"RAG node failed: {e}")
            state["errors"].append(f"RAG error: {str(e)}")
            # RAG failure is not critical, continue

        return state

    @trace_function("human_input_node")
    def _human_input_node(self, state: AgentState) -> AgentState:
        """Human-in-the-loop node"""
        logger.info("Human input node executing")

        try:
            # Generate clarification question
            clarification_q = self.orchestrator._generate_clarification_question(
                state["question"],
                state["plan"],
                {},
            )

            state["needs_clarification"] = True
            state["clarification_question"] = clarification_q

        except Exception as e:
            logger.error(f"Human input node failed: {e}")
            state["errors"].append(f"Human input error: {str(e)}")

        return state

    @trace_function("synthesis_node")
    def _synthesis_node(self, state: AgentState) -> AgentState:
        """Synthesis node - creates final answer"""
        logger.info("Synthesis node executing")

        try:
            result = self.synthesis.synthesize(
                question=state["question"],
                agent_results=state["agent_results"],
                execution_log=state["execution_log"],
                conversation_history=state["conversation_history"],
            )

            if result.get("success"):
                state["final_answer"] = result["answer"]
                state["synthesis_result"] = result
                state["is_complete"] = True
                state["success"] = True

                import time
                state["end_time"] = time.time()

            else:
                state["errors"].append("Synthesis failed")
                state["should_replan"] = True

        except Exception as e:
            logger.error(f"Synthesis node failed: {e}")
            state["errors"].append(f"Synthesis error: {str(e)}")
            state["should_replan"] = True

        return state

    @trace_function("replan_node")
    def _replan_node(self, state: AgentState) -> AgentState:
        """Replan node - creates new plan after failure"""
        logger.info("Replan node executing")

        try:
            new_plan = self.orchestrator._replan(
                state["plan"],
                state["execution_log"],
                state["question"],
            )

            state["plan"] = new_plan
            state["should_replan"] = False
            state["current_step"] = 0

        except Exception as e:
            logger.error(f"Replan failed: {e}")
            state["errors"].append(f"Replan error: {str(e)}")
            state["is_complete"] = True
            state["success"] = False

        return state

    # Routing functions

    def _route_after_plan(
        self, state: AgentState
    ) -> Literal["table_understanding", "genie", "rag", "human_input", "synthesis", "end"]:
        """Route after planning"""

        if state["is_complete"]:
            return "end"

        plan = state.get("plan", {})
        steps = plan.get("steps", [])

        if not steps:
            return "end"

        # Check confidence threshold
        confidence = plan.get("confidence", 1.0)
        if confidence < config.agent.orchestrator_confidence_threshold:
            return "human_input"

        # Get next step
        current_step = state["current_step"]
        if current_step >= len(steps):
            return "synthesis"

        next_step = steps[current_step]
        agent_name = next_step.get("agent", "").upper()

        if agent_name == "TABLE_UNDERSTANDING":
            return "table_understanding"
        elif agent_name == "GENIE":
            return "genie"
        elif agent_name == "RAG":
            return "rag"
        else:
            return "synthesis"

    def _route_after_agent(
        self, state: AgentState
    ) -> Literal["table_understanding", "genie", "rag", "synthesis", "replan", "end"]:
        """Route after agent execution"""

        if state["is_complete"]:
            return "end"

        if state["should_replan"]:
            return "replan"

        # Get next step
        plan = state.get("plan", {})
        steps = plan.get("steps", [])
        current_step = state["current_step"]

        if current_step >= len(steps):
            return "synthesis"

        next_step = steps[current_step]
        agent_name = next_step.get("agent", "").upper()

        if agent_name == "TABLE_UNDERSTANDING":
            return "table_understanding"
        elif agent_name == "GENIE":
            return "genie"
        elif agent_name == "RAG":
            return "rag"
        else:
            return "synthesis"

    def _route_after_human(self, state: AgentState) -> Literal["plan", "end"]:
        """Route after human input"""

        if state.get("user_clarification"):
            # User provided clarification, replan with new info
            return "plan"
        else:
            # No clarification, end
            return "end"

    def invoke(self, question: str, session_id: str, conversation_history=None):
        """
        Invoke the graph with a question.

        Args:
            question: User question
            session_id: Session ID
            conversation_history: Previous conversation

        Returns:
            Final state
        """
        # Create initial state
        initial_state = create_initial_state(
            question=question,
            session_id=session_id,
            conversation_history=conversation_history,
        )

        # Run the graph
        config_dict = {"configurable": {"thread_id": session_id}}

        final_state = self.graph.invoke(initial_state, config=config_dict)

        return final_state

    def stream(self, question: str, session_id: str, conversation_history=None):
        """
        Stream graph execution.

        Args:
            question: User question
            session_id: Session ID
            conversation_history: Previous conversation

        Yields:
            State updates
        """
        initial_state = create_initial_state(
            question=question,
            session_id=session_id,
            conversation_history=conversation_history,
        )

        config_dict = {"configurable": {"thread_id": session_id}}

        for state in self.graph.stream(initial_state, config=config_dict):
            yield state


# Global graph instance
_multi_agent_graph = None


def get_multi_agent_graph() -> MultiAgentGraph:
    """Get global multi-agent graph instance"""
    global _multi_agent_graph
    if _multi_agent_graph is None:
        _multi_agent_graph = MultiAgentGraph()
    return _multi_agent_graph
