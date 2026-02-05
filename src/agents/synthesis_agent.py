"""
Synthesis Agent - Combines results from multiple agents into coherent final response.
"""

import json
from typing import Dict, Any, List, Optional

from langchain_openai import AzureChatOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from src.core.config import config
from src.utils.logging import get_logger, trace_function
from src.services.mlflow_tracker import track_agent

logger = get_logger(__name__)


class SynthesisAgent:
    """
    Agent responsible for synthesizing results from multiple agents into a coherent final response.
    """

    def __init__(self):
        self.llm = self._initialize_llm()
        logger.info("Initialized SynthesisAgent")

    def _initialize_llm(self) -> AzureChatOpenAI:
        """Initialize Azure OpenAI LLM"""
        try:
            if config.azure_openai.api_key:
                llm = AzureChatOpenAI(
                    azure_endpoint=config.azure_openai.endpoint,
                    api_key=config.azure_openai.api_key,
                    api_version=config.azure_openai.api_version,
                    deployment_name=config.azure_openai.gpt4o_deployment,
                    temperature=0.3,  # Slightly creative for synthesis
                    max_tokens=config.azure_openai.max_tokens,
                )
                return llm
        except Exception:
            pass

        # Fallback to managed identity
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default"
        )
        return AzureChatOpenAI(
            azure_endpoint=config.azure_openai.endpoint,
            azure_ad_token_provider=token_provider,
            api_version=config.azure_openai.api_version,
            deployment_name=config.azure_openai.gpt4o_deployment,
            temperature=0.3,
            max_tokens=config.azure_openai.max_tokens,
        )

    @trace_function("synthesize")
    @track_agent("synthesis_agent")
    def synthesize(
        self,
        question: str,
        agent_results: Dict[str, Any],
        execution_log: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize a final answer from multiple agent results.

        Args:
            question: Original user question
            agent_results: Results from various agents
            execution_log: Execution log from orchestrator
            conversation_history: Previous conversation

        Returns:
            Synthesized response
        """
        if conversation_history is None:
            conversation_history = []

        try:
            # Build context from agent results
            context_parts = []

            # Extract Genie results (SQL query data)
            genie_results = self._extract_genie_results(agent_results)
            if genie_results:
                context_parts.append(f"Data from SQL query:\n{genie_results}")

            # Extract RAG context
            rag_context = self._extract_rag_context(agent_results)
            if rag_context:
                context_parts.append(f"Relevant document context:\n{rag_context}")

            # Extract table metadata
            table_info = self._extract_table_info(agent_results)
            if table_info:
                context_parts.append(f"Table information:\n{table_info}")

            full_context = "\n\n".join(context_parts)

            synthesis_prompt = f"""You are synthesizing information from multiple sources to answer a user's question.

User question: {question}

Available information:
{full_context}

Conversation history: {json.dumps(conversation_history[-3:] if len(conversation_history) > 3 else conversation_history)}

Synthesize a clear, comprehensive answer that:
1. Directly answers the question
2. Uses data from the sources
3. Is well-formatted and easy to understand
4. Highlights key insights
5. Mentions data sources when relevant

Respond in a conversational, helpful tone."""

            response = self.llm.invoke(synthesis_prompt)
            final_answer = response.content.strip()

            logger.info("Synthesized final answer", answer_length=len(final_answer))

            return {
                "success": True,
                "answer": final_answer,
                "sources_used": self._identify_sources(agent_results),
                "context": full_context,
            }

        except Exception as e:
            logger.error(f"Failed to synthesize answer: {e}")

            # Fallback: simple concatenation
            return {
                "success": False,
                "answer": "I encountered an error while synthesizing the answer. Here are the raw results: " + str(agent_results),
                "error": str(e),
            }

    def _extract_genie_results(self, agent_results: Dict[str, Any]) -> Optional[str]:
        """Extract and format Genie SQL results"""
        for step_num, result in agent_results.items():
            if isinstance(result, dict) and result.get("sql_query"):
                # Format the data
                data = result.get("data", [])
                sql = result.get("sql_query")

                if not data:
                    return f"SQL Query executed: {sql}\nNo results returned."

                # Format as table
                formatted = f"SQL Query: {sql}\n\nResults:\n"

                # Limit to first 10 rows
                display_data = data[:10]

                for row in display_data:
                    formatted += json.dumps(row, indent=2) + "\n"

                if len(data) > 10:
                    formatted += f"\n... ({len(data) - 10} more rows)"

                return formatted

        return None

    def _extract_rag_context(self, agent_results: Dict[str, Any]) -> Optional[str]:
        """Extract RAG document context"""
        for step_num, result in agent_results.items():
            if isinstance(result, list):
                # Check if it's RAG context (list of dicts with 'text' and 'file_name')
                if result and isinstance(result[0], dict) and "text" in result[0]:
                    context_parts = []

                    for i, context in enumerate(result[:3], 1):  # Top 3
                        text = context.get("text", "")[:300]  # Limit length
                        file_name = context.get("file_name", "Unknown")
                        context_parts.append(f"[{i}] From {file_name}:\n{text}...")

                    return "\n\n".join(context_parts)

        return None

    def _extract_table_info(self, agent_results: Dict[str, Any]) -> Optional[str]:
        """Extract table understanding info"""
        for step_num, result in agent_results.items():
            if isinstance(result, list):
                # Check if it's table metadata
                if result and isinstance(result[0], dict) and "table_name" in result[0]:
                    table_parts = []

                    for table in result:
                        name = table.get("table_name")
                        desc = table.get("description", "")
                        columns = table.get("columns", [])

                        table_parts.append(
                            f"Table: {name}\n"
                            f"Description: {desc}\n"
                            f"Columns: {', '.join(columns)}"
                        )

                    return "\n\n".join(table_parts)

        return None

    def _identify_sources(self, agent_results: Dict[str, Any]) -> List[str]:
        """Identify which sources were used"""
        sources = []

        for step_num, result in agent_results.items():
            if isinstance(result, dict):
                if result.get("sql_query"):
                    sources.append("Unity Catalog (SQL)")
                elif "description" in result:
                    sources.append("Table Metadata")

            elif isinstance(result, list) and result:
                if isinstance(result[0], dict):
                    if "text" in result[0] and "file_name" in result[0]:
                        sources.append("Documents (RAG)")
                    elif "table_name" in result[0]:
                        sources.append("Table Metadata")

        return list(set(sources))


# Global synthesis agent
_synthesis_agent = None


def get_synthesis_agent() -> SynthesisAgent:
    """Get global synthesis agent"""
    global _synthesis_agent
    if _synthesis_agent is None:
        _synthesis_agent = SynthesisAgent()
    return _synthesis_agent
