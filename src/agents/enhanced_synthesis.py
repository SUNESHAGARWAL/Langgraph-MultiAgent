"""
Enhanced Synthesis Agent - Integrates Agentic RAG contextualization with Genie data.
This creates truly cohesive answers by combining data with business context.
"""

import json
from typing import Dict, Any, List, Optional

from langchain_openai import AzureChatOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from src.core.config import config
from src.utils.logging import get_logger, trace_function
from src.services.mlflow_tracker import track_agent

logger = get_logger(__name__)


class EnhancedSynthesisAgent:
    """
    Enhanced synthesis that creates cohesive answers by:
    1. Understanding Genie SQL data
    2. Integrating RAG business context
    3. Creating narrative that combines both
    4. Adding insights and interpretation
    """

    def __init__(self):
        self.llm = self._initialize_llm()
        logger.info("Initialized EnhancedSynthesisAgent")

    def _initialize_llm(self) -> AzureChatOpenAI:
        """Initialize Azure OpenAI LLM"""
        try:
            if config.azure_openai.api_key:
                return AzureChatOpenAI(
                    azure_endpoint=config.azure_openai.endpoint,
                    api_key=config.azure_openai.api_key,
                    api_version=config.azure_openai.api_version,
                    deployment_name=config.azure_openai.gpt4o_deployment,
                    temperature=0.3,
                    max_tokens=config.azure_openai.max_tokens,
                )
        except Exception:
            pass

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

    @trace_function("synthesize_with_context")
    @track_agent("enhanced_synthesis_agent")
    def synthesize_with_context(
        self,
        question: str,
        genie_result: Optional[Dict[str, Any]] = None,
        rag_contextualization: Optional[Dict[str, Any]] = None,
        table_metadata: Optional[List[Dict]] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize answer integrating Genie data with RAG contextualization.

        This is the KEY method that creates cohesive understanding:
        1. Takes raw Genie SQL data
        2. Takes RAG contextualization (business context, definitions, insights)
        3. Weaves them together into coherent narrative
        4. Adds interpretation and insights

        Args:
            question: Original user question
            genie_result: Results from Genie agent (SQL + data)
            rag_contextualization: Agentic RAG contextualization (from contextualize_genie_output)
            table_metadata: Table information
            conversation_history: Previous conversation

        Returns:
            Cohesive synthesized answer
        """
        if conversation_history is None:
            conversation_history = []

        try:
            # Build comprehensive context
            synthesis_prompt = self._build_synthesis_prompt(
                question=question,
                genie_result=genie_result,
                rag_contextualization=rag_contextualization,
                table_metadata=table_metadata,
                conversation_history=conversation_history,
            )

            logger.info("Synthesizing cohesive answer with context integration")

            # Generate synthesis
            response = self.llm.invoke(synthesis_prompt)
            final_answer = response.content.strip()

            # Identify sources
            sources_used = self._identify_sources(genie_result, rag_contextualization, table_metadata)

            logger.info(
                "Synthesized cohesive answer",
                answer_length=len(final_answer),
                sources=len(sources_used),
            )

            return {
                "success": True,
                "answer": final_answer,
                "sources_used": sources_used,
                "has_genie_data": genie_result is not None,
                "has_rag_context": rag_contextualization is not None and len(rag_contextualization.get("contexts", [])) > 0,
                "rag_insights": rag_contextualization.get("insights") if rag_contextualization else None,
            }

        except Exception as e:
            logger.error(f"Failed to synthesize answer: {e}")
            return {
                "success": False,
                "answer": f"Error synthesizing answer: {str(e)}",
                "error": str(e),
            }

    def _build_synthesis_prompt(
        self,
        question: str,
        genie_result: Optional[Dict],
        rag_contextualization: Optional[Dict],
        table_metadata: Optional[List[Dict]],
        conversation_history: List[Dict],
    ) -> str:
        """
        Build comprehensive synthesis prompt that integrates all information.

        This prompt is designed to create COHESIVE answers that:
        - Present the data from Genie
        - Explain it using RAG business context
        - Add interpretation and insights
        - Create a narrative flow
        """
        prompt_parts = []

        # System instruction
        prompt_parts.append("""You are synthesizing a comprehensive answer that integrates data with business context.

Your task is to create a COHESIVE answer that:
1. Directly answers the user's question
2. Presents the data (from SQL query)
3. Explains the business context and meaning (from documents)
4. Adds interpretation and insights
5. Creates a natural narrative flow

Be conversational but precise. Connect the data to its business meaning.""")

        # User question
        prompt_parts.append(f"\nUser Question: {question}")

        # Conversation history (for context)
        if conversation_history:
            recent_history = conversation_history[-3:]  # Last 3 turns
            prompt_parts.append(f"\nRecent Conversation:")
            for msg in recent_history:
                role = msg.get("role", "")
                content = msg.get("content", "")[:200]  # Truncate
                prompt_parts.append(f"{role}: {content}")

        # Genie Data
        if genie_result:
            sql_query = genie_result.get("sql_query", "")
            data = genie_result.get("data", [])
            columns = genie_result.get("columns", [])

            prompt_parts.append(f"\n=== DATA FROM SQL QUERY ===")

            if sql_query:
                prompt_parts.append(f"SQL: {sql_query}")

            if data:
                prompt_parts.append(f"Columns: {', '.join(columns)}")
                prompt_parts.append(f"Results ({len(data)} rows):")

                # Format data nicely
                for i, row in enumerate(data[:10], 1):  # Show first 10 rows
                    prompt_parts.append(f"{i}. {json.dumps(row)}")

                if len(data) > 10:
                    prompt_parts.append(f"... and {len(data) - 10} more rows")

        # RAG Contextualization (KEY PART!)
        if rag_contextualization and rag_contextualization.get("success"):
            contexts = rag_contextualization.get("contexts", [])
            insights = rag_contextualization.get("insights", "")

            if contexts or insights:
                prompt_parts.append(f"\n=== BUSINESS CONTEXT & EXPLANATION ===")

                if insights:
                    prompt_parts.append(f"RAG Analysis: {insights}")

                if contexts:
                    prompt_parts.append(f"\nRelevant Document Contexts ({len(contexts)} found):")

                    for i, ctx in enumerate(contexts[:3], 1):  # Top 3 contexts
                        text = ctx.get("text", "")[:300]  # Limit length
                        file_name = ctx.get("file_name", "Unknown")
                        similarity = ctx.get("similarity", 0)

                        prompt_parts.append(f"\n[Context {i}] From {file_name} (relevance: {similarity:.2f}):")
                        prompt_parts.append(text)

        # Table Metadata
        if table_metadata:
            prompt_parts.append(f"\n=== TABLE INFORMATION ===")

            for table in table_metadata[:2]:  # Top 2 tables
                name = table.get("table_name", "")
                description = table.get("description", "")
                columns = table.get("columns", [])

                prompt_parts.append(f"\nTable: {name}")
                if description:
                    prompt_parts.append(f"Description: {description}")
                if columns:
                    prompt_parts.append(f"Columns: {', '.join(columns[:5])}")

        # Final instruction
        prompt_parts.append(f"""\n=== YOUR TASK ===

Create a cohesive answer that:
1. Presents the data clearly
2. Explains what it means using the business context
3. Connects the numbers to their real-world meaning
4. Adds insights and interpretation

Be natural and conversational. Weave the data and context together into a unified narrative.""")

        return "\n".join(prompt_parts)

    def _identify_sources(
        self,
        genie_result: Optional[Dict],
        rag_contextualization: Optional[Dict],
        table_metadata: Optional[List[Dict]],
    ) -> List[str]:
        """Identify which sources were used"""
        sources = []

        if genie_result and genie_result.get("sql_query"):
            sources.append("Unity Catalog (SQL)")

        if rag_contextualization and rag_contextualization.get("contexts"):
            contexts = rag_contextualization["contexts"]
            if contexts:
                # Get unique file names
                file_names = set(ctx.get("file_name") for ctx in contexts if ctx.get("file_name"))
                if file_names:
                    sources.append(f"Documents ({len(file_names)} files)")

        if table_metadata:
            sources.append("Table Metadata")

        return sources

    @trace_function("synthesize_legacy")
    def synthesize_legacy(
        self,
        question: str,
        agent_results: Dict[str, Any],
        execution_log: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Legacy synthesis method for backward compatibility.
        Extracts data and calls synthesize_with_context.
        """
        # Extract components from agent_results
        genie_result = None
        rag_contextualization = None
        table_metadata = None

        # Extract Genie result
        for key, value in agent_results.items():
            if isinstance(value, dict):
                if value.get("sql_query"):
                    genie_result = value
                elif value.get("contexts"):  # RAG contextualization
                    rag_contextualization = value

            elif isinstance(value, list) and value:
                if isinstance(value[0], dict) and "table_name" in value[0]:
                    table_metadata = value

        return self.synthesize_with_context(
            question=question,
            genie_result=genie_result,
            rag_contextualization=rag_contextualization,
            table_metadata=table_metadata,
            conversation_history=conversation_history,
        )


# Global enhanced synthesis agent
_enhanced_synthesis_agent = None


def get_enhanced_synthesis_agent() -> EnhancedSynthesisAgent:
    """Get global enhanced synthesis agent"""
    global _enhanced_synthesis_agent
    if _enhanced_synthesis_agent is None:
        _enhanced_synthesis_agent = EnhancedSynthesisAgent()
    return _enhanced_synthesis_agent
