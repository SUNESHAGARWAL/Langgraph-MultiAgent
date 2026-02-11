"""
FastAPI Server for Multi-Agent Orchestrator

Provides REST API and WebSocket endpoints for real-time interaction.

Endpoints:
- POST /api/v1/query - Execute a single query
- WebSocket /ws/chat/{thread_id} - Real-time chat with streaming updates
- GET /api/v1/metrics - Get system metrics
- GET /api/v1/health - Health check
- POST /api/v1/clear-cache - Clear semantic cache (admin)

Usage:
    # Start server
    uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload

    # Query API
    curl -X POST http://localhost:8000/api/v1/query \\
      -H "Content-Type: application/json" \\
      -d '{"question": "What were sales last quarter?", "thread_id": "user-123"}'

    # WebSocket (JavaScript)
    const ws = new WebSocket('ws://localhost:8000/ws/chat/user-123');
    ws.send('What were sales last quarter?');
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid
import logging
import time

from langchain_core.messages import HumanMessage

# Import agent and metrics
from src.agent_enhanced import get_agent
from src.utils.metrics import get_metrics_tracker
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Agent Orchestrator API",
    description="Production-grade multi-agent system with Databricks Genie and RAG",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
agent = None
metrics_tracker = None


@app.on_event("startup")
async def startup_event():
    """Initialize agent and metrics tracker on startup."""
    global agent, metrics_tracker

    logger.info("Starting Multi-Agent Orchestrator API...")

    try:
        agent = get_agent()
        metrics_tracker = get_metrics_tracker()

        logger.info("✓ API server ready")

    except Exception as e:
        logger.error(f"Failed to initialize API: {e}")
        raise


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for /api/v1/query endpoint."""
    question: str = Field(..., description="User question", min_length=1)
    thread_id: Optional[str] = Field(None, description="Conversation thread ID")


class QueryResponse(BaseModel):
    """Response model for /api/v1/query endpoint."""
    query_id: str = Field(..., description="Unique query identifier")
    answer: str = Field(..., description="Final answer")
    thread_id: str = Field(..., description="Conversation thread ID")
    iterations: int = Field(..., description="Number of iterations")
    duration: float = Field(..., description="Query duration in seconds")
    cost: float = Field(..., description="Estimated cost in USD")
    cache_hit: bool = Field(..., description="Whether result was cached")
    success: bool = Field(..., description="Whether query succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")


class MetricsResponse(BaseModel):
    """Response model for /api/v1/metrics endpoint."""
    total_queries: int
    successful: int
    failed: int
    success_rate: float
    total_cost: float
    average_cost: float
    total_duration: float
    average_duration: float


class HealthResponse(BaseModel):
    """Response model for /api/v1/health endpoint."""
    status: str
    version: str
    agent_ready: bool
    timestamp: str


# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.post("/api/v1/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """
    Execute a single query.

    Args:
        request: QueryRequest with question and optional thread_id

    Returns:
        QueryResponse with answer and metrics

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/query \\
          -H "Content-Type: application/json" \\
          -d '{
            "question": "What were our top 5 products by revenue?",
            "thread_id": "user-123"
          }'
        ```
    """
    if not agent or not metrics_tracker:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    query_id = str(uuid.uuid4())
    thread_id = request.thread_id or str(uuid.uuid4())

    logger.info(f"Query {query_id}: {request.question[:100]}...")

    # Start metrics tracking
    metrics = metrics_tracker.start_query(query_id, request.question, thread_id)

    try:
        # Prepare initial state
        initial_state = {
            "messages": [HumanMessage(content=request.question)],
            "next_agent": "",
            "iterations": 0,
            "final_answer": "",
            "query_id": query_id,
            "parallel_agents": None,
            "validation_result": None,
            "validation_feedback": None,
        }

        # Invoke agent
        result = agent.invoke(
            initial_state,
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "query_id": query_id
                }
            }
        )

        # Extract results
        final_answer = result.get("final_answer", "")
        iterations = result.get("iterations", 0)

        # End metrics tracking
        metrics_tracker.end_query(
            query_id,
            success=True,
            iterations=iterations,
            final_answer=final_answer
        )

        # Get metrics
        query_metrics = metrics_tracker.get_query_metrics(query_id)

        return QueryResponse(
            query_id=query_id,
            answer=final_answer,
            thread_id=thread_id,
            iterations=iterations,
            duration=query_metrics.duration() if query_metrics else 0.0,
            cost=query_metrics.estimated_cost() if query_metrics else 0.0,
            cache_hit=query_metrics.cache_hits > 0 if query_metrics else False,
            success=True,
            error=None
        )

    except Exception as e:
        logger.error(f"Query {query_id} failed: {e}")

        # End metrics tracking with error
        metrics_tracker.end_query(
            query_id,
            success=False,
            iterations=0,
            error=str(e)
        )

        return QueryResponse(
            query_id=query_id,
            answer=f"Error: {str(e)}",
            thread_id=thread_id,
            iterations=0,
            duration=0.0,
            cost=0.0,
            cache_hit=False,
            success=False,
            error=str(e)
        )


@app.get("/api/v1/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    Get aggregate system metrics.

    Returns:
        MetricsResponse with system statistics

    Example:
        ```bash
        curl http://localhost:8000/api/v1/metrics
        ```
    """
    if not metrics_tracker:
        raise HTTPException(status_code=503, detail="Metrics tracker not initialized")

    stats = metrics_tracker.get_aggregate_stats()

    return MetricsResponse(**stats)


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        HealthResponse with service status

    Example:
        ```bash
        curl http://localhost:8000/api/v1/health
        ```
    """
    import datetime

    return HealthResponse(
        status="healthy" if agent else "unhealthy",
        version="3.0.0",
        agent_ready=agent is not None,
        timestamp=datetime.datetime.now().isoformat()
    )


@app.post("/api/v1/clear-cache")
async def clear_cache():
    """
    Clear semantic cache (admin endpoint).

    Returns:
        Success message

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/clear-cache
        ```
    """
    # This would need proper implementation to access cache
    # For now, return a placeholder
    return {
        "status": "success",
        "message": "Cache cleared (implementation needed)"
    }


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@app.websocket("/ws/chat/{thread_id}")
async def websocket_chat(websocket: WebSocket, thread_id: str):
    """
    WebSocket endpoint for real-time chat with streaming updates.

    Args:
        websocket: WebSocket connection
        thread_id: Conversation thread ID

    Message Format (Sent):
        ```json
        {"type": "progress", "agent": "SQL_Specialist", "message": "Querying database..."}
        {"type": "answer", "content": "...", "query_id": "..."}
        {"type": "error", "message": "..."}
        ```

    Example (JavaScript):
        ```javascript
        const ws = new WebSocket('ws://localhost:8000/ws/chat/user-123');

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'progress') {
                console.log('Progress:', data.message);
            } else if (data.type === 'answer') {
                console.log('Answer:', data.content);
            }
        };

        ws.send('What were sales last quarter?');
        ```
    """
    await websocket.accept()

    if not agent or not metrics_tracker:
        await websocket.send_json({
            "type": "error",
            "message": "Agent not initialized"
        })
        await websocket.close()
        return

    logger.info(f"WebSocket connected: thread_id={thread_id}")

    try:
        while True:
            # Receive question
            question = await websocket.receive_text()

            if not question.strip():
                continue

            query_id = str(uuid.uuid4())

            logger.info(f"WebSocket query {query_id}: {question[:100]}...")

            # Send processing status
            await websocket.send_json({
                "type": "status",
                "message": "Processing your question..."
            })

            # Start metrics
            metrics_tracker.start_query(query_id, question, thread_id)

            try:
                # Prepare initial state
                initial_state = {
                    "messages": [HumanMessage(content=question)],
                    "next_agent": "",
                    "iterations": 0,
                    "final_answer": "",
                    "query_id": query_id,
                }

                # Stream results
                async for chunk in stream_agent_results(agent, initial_state, thread_id, query_id):
                    await websocket.send_json(chunk)

                # End metrics
                metrics_tracker.end_query(query_id, True, chunk.get("iterations", 0))

            except Exception as e:
                logger.error(f"WebSocket query {query_id} failed: {e}")

                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

                metrics_tracker.end_query(query_id, False, 0, error=str(e))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: thread_id={thread_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


async def stream_agent_results(agent, initial_state, thread_id, query_id):
    """
    Stream agent results for WebSocket.

    This is a placeholder - full streaming would require
    modifying the agent to support streaming mode.

    Args:
        agent: Agent instance
        initial_state: Initial state dict
        thread_id: Thread ID
        query_id: Query ID

    Yields:
        Dict with progress updates and final answer
    """
    # For now, we execute and return the final result
    # In a full implementation, we'd stream intermediate steps

    result = agent.invoke(
        initial_state,
        config={
            "configurable": {
                "thread_id": thread_id,
                "query_id": query_id
            }
        }
    )

    # Send final answer
    yield {
        "type": "answer",
        "content": result.get("final_answer", ""),
        "query_id": query_id,
        "iterations": result.get("iterations", 0)
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
