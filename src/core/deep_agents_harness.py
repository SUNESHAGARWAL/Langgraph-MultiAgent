"""
Deep Agents Harness Integration - Using deepagents library for advanced planning.
Implements the harness pattern with filesystem backend and tool execution.
"""

from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import json
import subprocess
from dataclasses import dataclass, asdict

from src.utils.logging import get_logger, trace_function
from src.core.config import config

logger = get_logger(__name__)


@dataclass
class AgentTool:
    """Tool definition for Deep Agents"""
    name: str
    description: str
    function: Callable
    parameters: Dict[str, Any]


@dataclass
class PlanStep:
    """Single step in execution plan"""
    step_id: str
    agent: str
    action: str
    tool: Optional[str] = None
    dependencies: List[str] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class ExecutionPlan:
    """Complete execution plan"""
    plan_id: str
    question: str
    steps: List[PlanStep]
    confidence: float
    created_at: str
    status: str = "pending"


class DeepAgentsHarness:
    """
    Deep Agents Harness - Advanced planning and tool execution.

    Features:
    - Filesystem-backed state persistence
    - Subprocess-based agent execution
    - Tool-based architecture
    - Advanced planning with dependencies
    - Error recovery and replanning
    """

    def __init__(self, workspace_path: Optional[str] = None):
        """
        Initialize Deep Agents Harness.

        Args:
            workspace_path: Path for filesystem backend (default: ./data/deep_agents)
        """
        self.workspace_path = Path(workspace_path or "./data/deep_agents")
        self.workspace_path.mkdir(parents=True, exist_ok=True)

        self.plans_dir = self.workspace_path / "plans"
        self.tools_dir = self.workspace_path / "tools"
        self.state_dir = self.workspace_path / "state"

        for directory in [self.plans_dir, self.tools_dir, self.state_dir]:
            directory.mkdir(exist_ok=True)

        # Tool registry
        self.tools: Dict[str, AgentTool] = {}

        logger.info(
            "Initialized Deep Agents Harness",
            workspace=str(self.workspace_path),
        )

    @trace_function("register_tool")
    def register_tool(
        self,
        name: str,
        description: str,
        function: Callable,
        parameters: Dict[str, Any],
    ):
        """
        Register a tool for agent use.

        Args:
            name: Tool name
            description: What the tool does
            function: Callable function
            parameters: Parameter schema
        """
        tool = AgentTool(
            name=name,
            description=description,
            function=function,
            parameters=parameters,
        )

        self.tools[name] = tool

        # Persist tool definition
        tool_file = self.tools_dir / f"{name}.json"
        with open(tool_file, "w") as f:
            json.dump({
                "name": name,
                "description": description,
                "parameters": parameters,
            }, f, indent=2)

        logger.info(f"Registered tool: {name}")

    @trace_function("create_plan")
    def create_plan(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        available_agents: Optional[List[str]] = None,
    ) -> ExecutionPlan:
        """
        Create execution plan using Deep Agents planning.

        Args:
            question: User question
            context: Additional context
            available_agents: List of available agent names

        Returns:
            ExecutionPlan with steps
        """
        import uuid
        from datetime import datetime

        plan_id = str(uuid.uuid4())[:8]

        # In a real implementation, this would use the deepagents library
        # For now, we'll implement the pattern manually

        logger.info(f"Creating execution plan", question=question, plan_id=plan_id)

        # Analyze question and create steps
        steps = self._plan_steps(question, context, available_agents)

        plan = ExecutionPlan(
            plan_id=plan_id,
            question=question,
            steps=steps,
            confidence=0.9,  # Would be calculated by planning LLM
            created_at=datetime.utcnow().isoformat(),
            status="pending",
        )

        # Persist plan to filesystem
        self._save_plan(plan)

        logger.info(
            f"Created execution plan",
            plan_id=plan_id,
            num_steps=len(steps),
        )

        return plan

    def _plan_steps(
        self,
        question: str,
        context: Optional[Dict],
        available_agents: Optional[List[str]],
    ) -> List[PlanStep]:
        """
        Plan execution steps.

        This is where Deep Agents planning would happen.
        Uses available tools and agents to create optimal plan.
        """
        steps = []

        # Example planning logic (simplified)
        # In production, this would use deepagents planning LLM

        if not available_agents:
            available_agents = ["table_understanding", "genie", "rag"]

        # Heuristic: If question mentions data/SQL/query -> use Genie
        # If question needs context -> use RAG
        # Always check tables first

        import uuid

        # Step 1: Table Understanding
        steps.append(PlanStep(
            step_id=f"step_{uuid.uuid4().hex[:8]}",
            agent="table_understanding",
            action="search_tables",
            tool="search_tables_tool",
            dependencies=[],
        ))

        # Step 2: Genie Query
        steps.append(PlanStep(
            step_id=f"step_{uuid.uuid4().hex[:8]}",
            agent="genie",
            action="execute_query",
            tool="genie_query_tool",
            dependencies=[steps[0].step_id],
        ))

        # Step 3: Agentic RAG Contextualization
        steps.append(PlanStep(
            step_id=f"step_{uuid.uuid4().hex[:8]}",
            agent="agentic_rag",
            action="contextualize_genie_output",
            tool="rag_contextualize_tool",
            dependencies=[steps[1].step_id],
        ))

        return steps

    @trace_function("execute_plan")
    def execute_plan(
        self,
        plan: ExecutionPlan,
        agent_executors: Dict[str, Callable],
    ) -> Dict[str, Any]:
        """
        Execute plan using registered tools and agents.

        Args:
            plan: ExecutionPlan to execute
            agent_executors: Dict mapping agent names to execution functions

        Returns:
            Execution results
        """
        logger.info(f"Executing plan", plan_id=plan.plan_id)

        plan.status = "running"
        self._save_plan(plan)

        results = {}
        failed_steps = []

        # Execute steps in dependency order
        for step in plan.steps:
            # Check dependencies
            if step.dependencies:
                deps_met = all(
                    self._get_step_by_id(plan, dep_id).status == "completed"
                    for dep_id in step.dependencies
                )

                if not deps_met:
                    logger.warning(f"Dependencies not met for step {step.step_id}")
                    step.status = "failed"
                    step.error = "Dependencies not met"
                    failed_steps.append(step)
                    continue

            # Execute step
            try:
                step.status = "running"
                self._save_plan(plan)

                logger.info(f"Executing step", step_id=step.step_id, agent=step.agent)

                executor = agent_executors.get(step.agent)
                if not executor:
                    raise ValueError(f"No executor for agent: {step.agent}")

                # Get context from dependencies
                dep_results = {
                    dep_id: self._get_step_by_id(plan, dep_id).result
                    for dep_id in (step.dependencies or [])
                }

                # Execute
                result = executor(
                    action=step.action,
                    tool=step.tool,
                    dependencies=dep_results,
                    question=plan.question,
                )

                step.result = result
                step.status = "completed"
                results[step.step_id] = result

                logger.info(f"Step completed", step_id=step.step_id)

            except Exception as e:
                logger.error(f"Step failed: {e}", step_id=step.step_id)
                step.status = "failed"
                step.error = str(e)
                failed_steps.append(step)

            self._save_plan(plan)

        # Update plan status
        if failed_steps:
            plan.status = "failed"
        else:
            plan.status = "completed"

        self._save_plan(plan)

        return {
            "success": plan.status == "completed",
            "plan_id": plan.plan_id,
            "results": results,
            "failed_steps": [s.step_id for s in failed_steps],
        }

    def _get_step_by_id(self, plan: ExecutionPlan, step_id: str) -> Optional[PlanStep]:
        """Get step by ID"""
        for step in plan.steps:
            if step.step_id == step_id:
                return step
        return None

    def _save_plan(self, plan: ExecutionPlan):
        """Save plan to filesystem"""
        plan_file = self.plans_dir / f"{plan.plan_id}.json"

        with open(plan_file, "w") as f:
            # Convert to dict
            plan_dict = {
                "plan_id": plan.plan_id,
                "question": plan.question,
                "confidence": plan.confidence,
                "created_at": plan.created_at,
                "status": plan.status,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "agent": s.agent,
                        "action": s.action,
                        "tool": s.tool,
                        "dependencies": s.dependencies or [],
                        "status": s.status,
                        "result": s.result,
                        "error": s.error,
                    }
                    for s in plan.steps
                ],
            }

            json.dump(plan_dict, f, indent=2)

    @trace_function("load_plan")
    def load_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Load plan from filesystem"""
        plan_file = self.plans_dir / f"{plan_id}.json"

        if not plan_file.exists():
            return None

        with open(plan_file, "r") as f:
            data = json.load(f)

        steps = [
            PlanStep(
                step_id=s["step_id"],
                agent=s["agent"],
                action=s["action"],
                tool=s.get("tool"),
                dependencies=s.get("dependencies", []),
                status=s["status"],
                result=s.get("result"),
                error=s.get("error"),
            )
            for s in data["steps"]
        ]

        plan = ExecutionPlan(
            plan_id=data["plan_id"],
            question=data["question"],
            steps=steps,
            confidence=data["confidence"],
            created_at=data["created_at"],
            status=data["status"],
        )

        return plan

    @trace_function("replan")
    def replan(
        self,
        original_plan: ExecutionPlan,
        failure_info: Dict[str, Any],
    ) -> ExecutionPlan:
        """
        Create new plan based on failure information.

        Args:
            original_plan: Failed plan
            failure_info: Information about what failed

        Returns:
            New ExecutionPlan
        """
        logger.info(f"Replanning", original_plan_id=original_plan.plan_id)

        # In production, this would use deepagents to analyze failure and replan
        # For now, create a modified plan

        import uuid
        from datetime import datetime

        new_plan_id = str(uuid.uuid4())[:8]

        # Analyze failures and create new steps
        new_steps = []

        for step in original_plan.steps:
            if step.status == "failed":
                # Modify failed step
                new_step = PlanStep(
                    step_id=f"step_{uuid.uuid4().hex[:8]}",
                    agent=step.agent,
                    action=f"{step.action}_retry",
                    tool=step.tool,
                    dependencies=step.dependencies,
                )
                new_steps.append(new_step)
            else:
                # Keep successful step
                new_steps.append(step)

        new_plan = ExecutionPlan(
            plan_id=new_plan_id,
            question=original_plan.question,
            steps=new_steps,
            confidence=0.7,  # Lower confidence for replan
            created_at=datetime.utcnow().isoformat(),
            status="pending",
        )

        self._save_plan(new_plan)

        logger.info(f"Created replan", new_plan_id=new_plan_id)

        return new_plan

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all registered tools"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self.tools.values()
        ]


# Global harness instance
_deep_agents_harness = None


def get_deep_agents_harness() -> DeepAgentsHarness:
    """Get global Deep Agents harness instance"""
    global _deep_agents_harness
    if _deep_agents_harness is None:
        _deep_agents_harness = DeepAgentsHarness()
    return _deep_agents_harness
