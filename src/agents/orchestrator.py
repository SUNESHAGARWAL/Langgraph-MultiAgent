"""
Orchestrator Agent - Main coordinator with planning, routing, and feedback loops.
Uses Deep Agents patterns for complex multi-step reasoning.
"""

import json
from typing import Dict, Any, List, Optional
from enum import Enum

from langchain_openai import AzureChatOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from src.core.config import config
from src.agents.genie_agent import get_genie_agent
from src.agents.table_understanding import get_table_understanding_agent
from src.agents.rag_agent import get_rag_agent
from src.utils.logging import get_logger, trace_function
from src.services.mlflow_tracker import track_agent, get_mlflow_tracker

logger = get_logger(__name__)


class AgentType(Enum):
    """Available agent types"""

    GENIE = "genie"
    TABLE_UNDERSTANDING = "table_understanding"
    RAG = "rag"
    HUMAN_INPUT = "human_input"


class OrchestratorAgent:
    """
    Main orchestrator that:
    1. Analyzes user questions
    2. Creates execution plans
    3. Routes to appropriate agents
    4. Handles feedback loops and replanning
    5. Coordinates multi-agent workflows
    """

    def __init__(self):
        self.llm = self._initialize_llm()
        self.genie_agent = get_genie_agent()
        self.table_agent = get_table_understanding_agent()
        self.rag_agent = get_rag_agent()
        self.tracker = get_mlflow_tracker()

        self.max_iterations = config.agent.max_iterations
        self.confidence_threshold = config.agent.orchestrator_confidence_threshold

        logger.info(
            "Initialized OrchestratorAgent",
            max_iterations=self.max_iterations,
        )

    def _initialize_llm(self) -> AzureChatOpenAI:
        """Initialize Azure OpenAI LLM"""
        try:
            # Try with API key first
            if config.azure_openai.api_key:
                llm = AzureChatOpenAI(
                    azure_endpoint=config.azure_openai.endpoint,
                    api_key=config.azure_openai.api_key,
                    api_version=config.azure_openai.api_version,
                    deployment_name=config.azure_openai.gpt4o_deployment,
                    temperature=config.azure_openai.temperature,
                    max_tokens=config.azure_openai.max_tokens,
                )
                logger.info("Initialized Azure OpenAI LLM with API key")
                return llm

        except Exception as e:
            logger.warning(f"Failed to initialize with API key: {e}")

        # Fallback to managed identity
        try:
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default"
            )
            llm = AzureChatOpenAI(
                azure_endpoint=config.azure_openai.endpoint,
                azure_ad_token_provider=token_provider,
                api_version=config.azure_openai.api_version,
                deployment_name=config.azure_openai.gpt4o_deployment,
                temperature=config.azure_openai.temperature,
                max_tokens=config.azure_openai.max_tokens,
            )
            logger.info("Initialized Azure OpenAI LLM with managed identity")
            return llm

        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise

    @trace_function("orchestrate")
    @track_agent("orchestrator")
    def orchestrate(
        self,
        question: str,
        conversation_history: Optional[List[Dict]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main orchestration method.

        Args:
            question: User question
            conversation_history: Previous conversation turns
            context: Additional context

        Returns:
            Orchestration result with plan, agent outputs, and final answer
        """
        if conversation_history is None:
            conversation_history = []

        if context is None:
            context = {}

        iteration = 0
        plan = None
        execution_log = []

        logger.info(
            f"Starting orchestration",
            question=question,
            history_length=len(conversation_history),
        )

        while iteration < self.max_iterations:
            iteration += 1

            # Step 1: Create or update plan
            if plan is None:
                plan = self._create_plan(question, conversation_history, context)
            else:
                plan = self._replan(plan, execution_log, question)

            logger.info(
                f"Iteration {iteration}: Plan created",
                num_steps=len(plan.get("steps", [])),
            )

            execution_log.append({
                "iteration": iteration,
                "plan": plan,
                "executions": [],
            })

            # Step 2: Execute plan
            execution_result = self._execute_plan(
                plan,
                question,
                conversation_history,
                context,
            )

            execution_log[-1]["executions"] = execution_result["executions"]

            # Step 3: Check if plan succeeded
            if execution_result["success"]:
                logger.info(f"Plan execution successful after {iteration} iterations")

                return {
                    "success": True,
                    "question": question,
                    "plan": plan,
                    "execution_log": execution_log,
                    "result": execution_result["result"],
                    "iterations": iteration,
                }

            # Step 4: Handle failure - check if we should ask for human input
            if self._should_ask_human(plan, execution_result):
                clarification = self._generate_clarification_question(
                    question,
                    plan,
                    execution_result,
                )

                return {
                    "success": False,
                    "needs_clarification": True,
                    "clarification_question": clarification,
                    "question": question,
                    "plan": plan,
                    "execution_log": execution_log,
                    "iterations": iteration,
                }

            # Continue to next iteration for replanning

        logger.warning(f"Max iterations reached without success")

        return {
            "success": False,
            "question": question,
            "execution_log": execution_log,
            "error": "Max iterations reached without successful completion",
            "iterations": iteration,
        }

    @trace_function("create_plan")
    def _create_plan(
        self,
        question: str,
        conversation_history: List[Dict],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create an execution plan for the question"""

        # Get available tables
        table_suggestions = self.table_agent.get_table_suggestions()

        planning_prompt = f"""You are an AI orchestrator planning how to answer a user's question.

Available agents:
1. GENIE - Executes SQL queries on Unity Catalog using natural language
2. TABLE_UNDERSTANDING - Provides information about available tables and their schemas
3. RAG - Retrieves information from uploaded documents

Available tables:
{chr(10).join(table_suggestions)}

User question: {question}

Conversation history: {json.dumps(conversation_history[-3:] if len(conversation_history) > 3 else conversation_history)}

Create a step-by-step plan to answer this question. Each step should specify:
- agent: Which agent to use (GENIE, TABLE_UNDERSTANDING, RAG)
- action: What the agent should do
- depends_on: Which previous steps this depends on (empty list if none)

Respond in JSON format:
{{
    "analysis": "Your analysis of the question",
    "confidence": 0.0-1.0,
    "steps": [
        {{
            "step": 1,
            "agent": "agent_name",
            "action": "description of what to do",
            "depends_on": []
        }}
    ]
}}"""

        try:
            response = self.llm.invoke(planning_prompt)
            content = response.content

            # Parse JSON response
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            plan = json.loads(content)

            logger.info(
                f"Created plan",
                confidence=plan.get("confidence"),
                num_steps=len(plan.get("steps", [])),
            )

            return plan

        except Exception as e:
            logger.error(f"Failed to create plan: {e}")

            # Fallback plan
            return {
                "analysis": "Fallback plan due to parsing error",
                "confidence": 0.5,
                "steps": [
                    {
                        "step": 1,
                        "agent": "GENIE",
                        "action": f"Answer the question: {question}",
                        "depends_on": [],
                    }
                ],
            }

    def _replan(
        self,
        previous_plan: Dict[str, Any],
        execution_log: List[Dict],
        question: str,
    ) -> Dict[str, Any]:
        """Create a new plan based on previous execution results"""

        replanning_prompt = f"""The previous plan failed. Analyze the execution log and create a better plan.

Original question: {question}

Previous plan:
{json.dumps(previous_plan, indent=2)}

Execution log:
{json.dumps(execution_log[-1], indent=2)}

Create a new, improved plan that addresses the failures. Use the same JSON format as before."""

        try:
            response = self.llm.invoke(replanning_prompt)
            content = response.content

            # Parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            new_plan = json.loads(content)

            logger.info(f"Created new plan after failure")

            return new_plan

        except Exception as e:
            logger.error(f"Failed to replan: {e}")
            return previous_plan  # Return previous plan if replanning fails

    def _execute_plan(
        self,
        plan: Dict[str, Any],
        question: str,
        conversation_history: List[Dict],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the plan step by step"""

        steps = plan.get("steps", [])
        results = {}
        executions = []

        for step in steps:
            step_num = step["step"]
            agent_name = step["agent"]
            action = step["action"]

            logger.info(f"Executing step {step_num}: {agent_name}")

            try:
                # Execute the agent
                if agent_name == "GENIE":
                    result = self.genie_agent.query(action)
                elif agent_name == "TABLE_UNDERSTANDING":
                    # Parse action to determine what table info is needed
                    result = self.table_agent.search_tables(question)
                elif agent_name == "RAG":
                    result = self.rag_agent.retrieve_context(action)
                else:
                    result = {"error": f"Unknown agent: {agent_name}"}

                results[step_num] = result

                executions.append({
                    "step": step_num,
                    "agent": agent_name,
                    "action": action,
                    "success": result.get("success", True) if isinstance(result, dict) else True,
                    "result": result,
                })

                # Check if this step failed
                if isinstance(result, dict) and not result.get("success", True):
                    logger.warning(f"Step {step_num} failed")

                    return {
                        "success": False,
                        "failed_step": step_num,
                        "executions": executions,
                        "result": None,
                    }

            except Exception as e:
                logger.error(f"Step {step_num} raised exception: {e}")

                executions.append({
                    "step": step_num,
                    "agent": agent_name,
                    "action": action,
                    "success": False,
                    "error": str(e),
                })

                return {
                    "success": False,
                    "failed_step": step_num,
                    "executions": executions,
                    "result": None,
                }

        # All steps succeeded
        return {
            "success": True,
            "executions": executions,
            "result": results,
        }

    def _should_ask_human(
        self,
        plan: Dict[str, Any],
        execution_result: Dict[str, Any],
    ) -> bool:
        """Determine if we should ask the human for clarification"""

        # Ask if:
        # 1. Confidence is low
        # 2. Multiple failures
        # 3. Ambiguous query

        confidence = plan.get("confidence", 1.0)

        if confidence < self.confidence_threshold:
            return True

        # Check for multiple failures (more than 2 iterations)
        # This is a simplified check

        return False

    def _generate_clarification_question(
        self,
        question: str,
        plan: Dict[str, Any],
        execution_result: Dict[str, Any],
    ) -> str:
        """Generate a clarification question for the user"""

        # Get table suggestions
        table_suggestions = self.table_agent.get_table_suggestions()

        clarification_prompt = f"""The system needs clarification to answer the user's question.

User question: {question}

Available tables:
{chr(10).join(table_suggestions[:5])}

Generate a helpful clarification question that:
1. Explains what information is available
2. Asks the user to be more specific
3. Provides suggestions

Respond with just the clarification question, no additional formatting."""

        try:
            response = self.llm.invoke(clarification_prompt)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Failed to generate clarification: {e}")
            return f"I need more information to answer your question. Available tables: {', '.join([t.split(':')[0] for t in table_suggestions[:3]])}. Which would you like to query?"


# Global orchestrator
_orchestrator = None


def get_orchestrator() -> OrchestratorAgent:
    """Get global orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator
