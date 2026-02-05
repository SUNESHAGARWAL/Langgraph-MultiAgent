# 🔧 Extending the Multi-Agent Orchestrator

This guide shows you **exactly how to add new agents, tools, and features** to the system.

---

## 📋 Table of Contents

1. [Adding a New Agent](#adding-a-new-agent)
2. [Adding to LangGraph](#adding-to-langgraph)
3. [System Architecture Explained](#system-architecture-explained)
4. [Adding New Tools](#adding-new-tools)
5. [Best Practices](#best-practices)
6. [Examples](#examples)

---

## Adding a New Agent

### Step 1: Create Agent File

Create `src/agents/my_new_agent.py`:

```python
"""
My New Agent - Description of what it does.
"""

from typing import Dict, Any, Optional

from src.core.config import config
from src.utils.logging import get_logger, trace_function
from src.services.mlflow_tracker import track_agent

logger = get_logger(__name__)


class MyNewAgent:
    """
    Description of your agent's purpose.
    """

    def __init__(self):
        """Initialize the agent with any required dependencies"""
        # Initialize any services you need
        logger.info("Initialized MyNewAgent")

    @trace_function("my_agent_process")  # Auto-tracing
    @track_agent("my_new_agent")  # Auto-MLflow tracking
    def process(
        self,
        input_data: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main processing method.

        Args:
            input_data: Input to process
            context: Additional context

        Returns:
            Result dictionary with 'success' and data
        """
        try:
            # Your agent logic here
            result = self._do_something(input_data)

            logger.info(
                "MyNewAgent processed successfully",
                input_length=len(input_data),
            )

            return {
                "success": True,
                "result": result,
                "agent": "my_new_agent",
            }

        except Exception as e:
            logger.error(f"MyNewAgent failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent": "my_new_agent",
            }

    def _do_something(self, input_data: str):
        """Private helper method"""
        # Your implementation
        return f"Processed: {input_data}"


# Global instance (singleton pattern)
_my_new_agent = None


def get_my_new_agent() -> MyNewAgent:
    """Get global instance"""
    global _my_new_agent
    if _my_new_agent is None:
        _my_new_agent = MyNewAgent()
    return _my_new_agent
```

### Step 2: Add Configuration (Optional)

If your agent needs configuration, add to `src/core/config.py`:

```python
class MyNewAgentConfig(BaseSettings):
    """My New Agent Configuration"""

    api_endpoint: str = Field(..., alias="MY_AGENT_API_ENDPOINT")
    timeout: int = Field(default=30, alias="MY_AGENT_TIMEOUT")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# In Config class:
class Config:
    def __init__(self):
        # ... existing configs ...
        self.my_new_agent = MyNewAgentConfig()
```

And add to `.env.example`:

```bash
# My New Agent
MY_AGENT_API_ENDPOINT=https://api.example.com
MY_AGENT_TIMEOUT=30
```

### Step 3: Add to LangGraph

Update `src/core/graph.py`:

```python
# 1. Import your agent
from src.agents.my_new_agent import get_my_new_agent

class MultiAgentGraph:
    def __init__(self):
        # ... existing agents ...
        self.my_new_agent = get_my_new_agent()  # Initialize

    def _build_graph(self):
        # ... existing code ...

        # Add node
        workflow.add_node("my_new_agent", self._my_new_agent_node)

        # Add edges (routing)
        workflow.add_conditional_edges(
            "plan",
            self._route_after_plan,
            {
                # ... existing routes ...
                "my_new_agent": "my_new_agent",  # Add route
            },
        )

        workflow.add_conditional_edges(
            "my_new_agent",
            self._route_after_agent,
            {
                "synthesis": "synthesis",
                "replan": "replan",
                "end": END,
            },
        )

    @trace_function("my_new_agent_node")
    def _my_new_agent_node(self, state: AgentState) -> AgentState:
        """My new agent node"""
        logger.info("MyNewAgent node executing")

        try:
            result = self.my_new_agent.process(
                state["question"],
                context={"session_id": state["session_id"]},
            )

            if result.get("success"):
                state["agent_results"]["my_new_agent"] = result
                state["current_step"] += 1
            else:
                state["errors"].append(f"MyNewAgent failed: {result.get('error')}")
                state["should_replan"] = True

        except Exception as e:
            logger.error(f"MyNewAgent node failed: {e}")
            state["errors"].append(f"MyNewAgent error: {str(e)}")
            state["should_replan"] = True

        return state

    def _route_after_plan(self, state: AgentState):
        # ... existing code ...

        agent_name = next_step.get("agent", "").upper()

        # Add routing logic
        if agent_name == "MY_NEW_AGENT":
            return "my_new_agent"
        # ... existing conditions ...
```

### Step 4: Update State (if needed)

If your agent needs specific state fields, update `src/core/state.py`:

```python
class AgentState(TypedDict):
    # ... existing fields ...

    # Add your agent's state
    my_agent_result: Optional[Dict[str, Any]]
```

### Step 5: Update Orchestrator Planning

Update `src/agents/orchestrator.py` to include your agent in planning:

```python
def _create_plan(self, question, ...):
    planning_prompt = f"""You are an AI orchestrator planning how to answer a user's question.

Available agents:
1. GENIE - Executes SQL queries on Unity Catalog
2. TABLE_UNDERSTANDING - Table information
3. RAG - Document retrieval
4. MY_NEW_AGENT - Description of what your agent does  # Add this

...

agent: Which agent to use (GENIE, TABLE_UNDERSTANDING, RAG, MY_NEW_AGENT)  # Add here
"""
```

### Step 6: Add Tests

Create `tests/test_my_new_agent.py`:

```python
import pytest
from src.agents.my_new_agent import get_my_new_agent


class TestMyNewAgent:
    def test_agent_initializes(self):
        agent = get_my_new_agent()
        assert agent is not None

    def test_process(self):
        agent = get_my_new_agent()
        result = agent.process("test input")

        assert result["success"] is True
        assert "result" in result

    def test_error_handling(self):
        agent = get_my_new_agent()
        # Test error cases
        pass
```

### Step 7: Update Documentation

Add to `SKILLS.md`:

```markdown
## 🆕 My New Agent

**Purpose:** Description of what it does

### Skills

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| **process** | Main processing function | Input string | Result dict |

### Example Use Cases

1. **Use Case 1:** Description
2. **Use Case 2:** Description
```

---

## System Architecture Explained

### 🏗️ Complete Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER QUERY                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MAIN.PY (Entry Point)                        │
│  - MultiAgentOrchestrator class                                 │
│  - Session management                                            │
│  - MLflow run context                                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│               CORE/GRAPH.PY (LangGraph StateGraph)              │
│                                                                  │
│  Nodes:                           Routing:                       │
│  ├─ plan                          ├─ Conditional edges           │
│  ├─ table_understanding           ├─ Agent selection             │
│  ├─ genie                         ├─ Error handling              │
│  ├─ rag                           └─ Replan triggers             │
│  ├─ human_input                                                  │
│  ├─ synthesis                                                    │
│  └─ replan                                                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┬──────────────┐
        │                │                │              │
        ▼                ▼                ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐
│ ORCHESTRATOR │  │    GENIE     │  │  TABLE   │  │   RAG    │
│    AGENT     │  │    AGENT     │  │   AGENT  │  │  AGENT   │
│              │  │              │  │          │  │          │
│ - Planning   │  │ - SQL Query  │  │ - EDA    │  │ - Docs   │
│ - Routing    │  │ - Cache Hit  │  │ - Schema │  │ - Search │
│ - Replanning │  │ - Execution  │  │ - Vector │  │ - Embed  │
└──────┬───────┘  └──────┬───────┘  └─────┬────┘  └────┬─────┘
       │                 │                 │            │
       └─────────────────┴─────────────────┴────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SERVICES LAYER                                │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Smart Cache  │  │ Vector Store │  │ Blob Storage │         │
│  │ (Redis/FAISS)│  │   (FAISS)    │  │   (Azure)    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   MLflow     │  │ File Monitor │  │  Embeddings  │         │
│  │   Tracker    │  │  (Watchdog)  │  │ (Azure OpenAI)│         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SYNTHESIS AGENT                                │
│  - Combines all agent results                                    │
│  - Formats final answer                                          │
│  - Adds source attribution                                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FINAL RESPONSE                               │
│  - Answer text                                                   │
│  - Sources used                                                  │
│  - Execution log                                                 │
│  - Performance metrics                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 📊 Data Flow

**1. Query Initialization:**
```python
main.py → MultiAgentOrchestrator.query()
    ↓
Creates AgentState with question, session_id, conversation_history
    ↓
Starts MLflow run
    ↓
Calls graph.invoke(state)
```

**2. LangGraph Execution:**
```python
graph.py → StateGraph.invoke()
    ↓
Entry: plan node
    ├─ Creates execution plan using GPT-4o
    ├─ Determines which agents needed
    └─ Sets confidence score
    ↓
Routing: _route_after_plan()
    ├─ Checks confidence threshold
    ├─ Reads next step from plan
    └─ Routes to appropriate agent node
    ↓
Agent Nodes Execute:
    ├─ table_understanding_node → searches tables
    ├─ genie_node → executes SQL
    ├─ rag_node → retrieves documents
    └─ Updates state with results
    ↓
Routing: _route_after_agent()
    ├─ Checks for errors (should_replan=True?)
    ├─ Gets next step
    └─ Routes to next agent OR synthesis
    ↓
Synthesis Node:
    ├─ Combines all agent_results
    ├─ Formats final answer
    └─ Sets is_complete=True
    ↓
END
```

**3. Response Return:**
```python
graph returns final_state
    ↓
main.py extracts answer
    ↓
Updates conversation history
    ↓
Logs metrics to MLflow
    ↓
Returns response dict to user
```

### 🔄 Feedback Loop

```python
Agent fails
    ↓
Sets should_replan=True in state
    ↓
_route_after_agent() returns "replan"
    ↓
replan_node executes:
    ├─ Calls orchestrator._replan()
    ├─ Creates new plan with failure info
    └─ Resets current_step = 0
    ↓
Routes back to "plan" node
    ↓
Executes new plan
```

### 📦 Module Structure

```
src/
├── main.py                    # Entry point, user interface
│   └── MultiAgentOrchestrator class
│
├── core/                      # Core system components
│   ├── config.py              # All configuration (Pydantic)
│   ├── state.py               # AgentState definition
│   └── graph.py               # LangGraph StateGraph (NEW!)
│
├── agents/                    # All specialized agents
│   ├── orchestrator.py        # Planning & routing logic
│   ├── genie_agent.py         # Databricks Genie integration
│   ├── table_understanding.py # EDA & table discovery
│   ├── rag_agent.py           # Document RAG system
│   ├── synthesis_agent.py     # Answer synthesis
│   └── human_loop.py          # Human interaction
│
├── services/                  # Supporting services
│   ├── caching.py             # Smart cache (Redis/FAISS)
│   ├── vector_store.py        # FAISS vector operations
│   ├── storage.py             # Azure Blob Storage
│   ├── mlflow_tracker.py      # Experiment tracking
│   └── file_monitor.py        # Watchdog file monitoring
│
└── utils/                     # Utilities
    ├── logging.py             # Structured logging
    ├── embeddings.py          # Azure OpenAI embeddings
    └── parsers.py             # Document parsers
```

---

## Adding New Tools

### Create a Tool Function

```python
# src/agents/tools/my_tool.py

from langchain.tools import tool

@tool
def my_custom_tool(query: str) -> str:
    """
    Description of what the tool does.

    Args:
        query: Input query

    Returns:
        Tool result
    """
    # Your implementation
    return f"Result for {query}"
```

### Add to Agent

```python
# In your agent
from langchain.agents import AgentExecutor
from src.agents.tools.my_tool import my_custom_tool

class MyAgent:
    def __init__(self):
        self.tools = [my_custom_tool]  # Add tool
```

---

## Best Practices

### ✅ Do's

1. **Always use decorators:**
   ```python
   @trace_function("my_function")  # Tracing
   @track_agent("my_agent")         # MLflow
   def my_function(...):
   ```

2. **Return standardized format:**
   ```python
   return {
       "success": bool,
       "result": any,  # if successful
       "error": str,   # if failed
       "agent": "agent_name",
   }
   ```

3. **Use logger:**
   ```python
   logger.info("Operation succeeded", key1=value1, key2=value2)
   logger.error("Operation failed: {e}", exc_info=True)
   ```

4. **Handle errors gracefully:**
   ```python
   try:
       result = do_something()
   except SpecificError as e:
       logger.error(f"Specific error: {e}")
       return {"success": False, "error": str(e)}
   except Exception as e:
       logger.error(f"Unexpected error: {e}", exc_info=True)
       return {"success": False, "error": "Unexpected error"}
   ```

5. **Use config:**
   ```python
   from src.core.config import config
   timeout = config.my_agent.timeout
   ```

### ❌ Don'ts

1. **Don't hardcode values** - Use config
2. **Don't swallow exceptions** - Always log
3. **Don't skip tests** - Write tests for new agents
4. **Don't forget documentation** - Update SKILLS.md
5. **Don't break conventions** - Follow existing patterns

---

## Examples

### Example 1: Weather Agent

```python
"""Weather Agent - Fetches weather information."""

import requests
from src.utils.logging import get_logger, trace_function
from src.services.mlflow_tracker import track_agent

logger = get_logger(__name__)


class WeatherAgent:
    """Fetches weather data from external API"""

    def __init__(self):
        self.api_key = config.weather.api_key
        self.base_url = "https://api.weather.com"
        logger.info("Initialized WeatherAgent")

    @trace_function("get_weather")
    @track_agent("weather_agent")
    def get_weather(self, location: str) -> dict:
        """Get weather for location"""
        try:
            response = requests.get(
                f"{self.base_url}/weather",
                params={"location": location, "apikey": self.api_key},
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()

            return {
                "success": True,
                "temperature": data["temp"],
                "conditions": data["conditions"],
                "location": location,
            }

        except requests.RequestException as e:
            logger.error(f"Weather API failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }


_weather_agent = None


def get_weather_agent():
    global _weather_agent
    if _weather_agent is None:
        _weather_agent = WeatherAgent()
    return _weather_agent
```

### Example 2: Adding to Graph

```python
# In graph.py

from src.agents.weather_agent import get_weather_agent

class MultiAgentGraph:
    def __init__(self):
        # ... existing ...
        self.weather = get_weather_agent()

    def _build_graph(self):
        # ... existing ...
        workflow.add_node("weather", self._weather_node)

        # Add routing
        workflow.add_conditional_edges(
            "plan",
            self._route_after_plan,
            {
                # ... existing ...
                "weather": "weather",
            },
        )

    @trace_function("weather_node")
    def _weather_node(self, state: AgentState) -> AgentState:
        """Weather node"""
        logger.info("Weather node executing")

        # Extract location from question
        # (you'd use LLM or regex here)
        location = "San Francisco"  # simplified

        result = self.weather.get_weather(location)

        if result["success"]:
            state["agent_results"]["weather"] = result
            state["current_step"] += 1
        else:
            state["errors"].append(f"Weather failed: {result['error']}")
            state["should_replan"] = True

        return state

    def _route_after_plan(self, state):
        # ... existing code ...

        if agent_name == "WEATHER":
            return "weather"
        # ... existing ...
```

---

## Testing Your New Agent

```bash
# Run tests
pytest tests/test_my_new_agent.py -v

# Integration test
python -c "
from src.agents.my_new_agent import get_my_new_agent
agent = get_my_new_agent()
result = agent.process('test input')
print(result)
"

# Full system test
python src/main.py
# Then ask a question that uses your agent
```

---

## Checklist for Adding New Agent

- [ ] Create agent file in `src/agents/`
- [ ] Add configuration to `src/core/config.py` (if needed)
- [ ] Add to `.env.example`
- [ ] Import in `src/core/graph.py`
- [ ] Add node to graph in `_build_graph()`
- [ ] Implement node method (`_my_agent_node`)
- [ ] Add routing logic in `_route_after_plan()`
- [ ] Update state in `src/core/state.py` (if needed)
- [ ] Update orchestrator planning prompt
- [ ] Write tests in `tests/`
- [ ] Update `SKILLS.md` documentation
- [ ] Test locally
- [ ] Commit changes

---

## Questions?

- **Architecture:** See CLAUDE.md
- **Agent Capabilities:** See SKILLS.md
- **Development Status:** See PROGRESS.md
- **Issues:** Check logs in `./data/logs/`

---

**Happy extending! 🚀**
