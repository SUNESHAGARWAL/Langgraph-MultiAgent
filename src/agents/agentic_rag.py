"""
Agentic RAG - Understands Genie output and finds contextual information.
This is a TRUE agentic RAG that doesn't just search, but understands and contextualizes.
"""

from typing import Dict, Any, List, Optional
from langchain_openai import AzureChatOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from src.services.vector_store import get_vector_store
from src.services.file_monitor import get_file_monitor
from src.services.storage import get_storage_service
from src.utils.parsers import get_document_parser
from src.utils.logging import get_logger, trace_function
from src.services.mlflow_tracker import track_agent
from src.core.config import config

logger = get_logger(__name__)


class AgenticRAG:
    """
    Truly Agentic RAG that:
    1. Analyzes Genie SQL results
    2. Understands what data was returned
    3. Searches for contextual documents that explain the data
    4. Provides business context and insights
    5. Helps synthesizer create cohesive answers
    """

    def __init__(self):
        self.vector_store = get_vector_store("rag_documents")
        self.storage = get_storage_service()
        self.parser = get_document_parser()
        self.file_monitor = None

        # LLM for understanding and reasoning
        self.llm = self._initialize_llm()

        logger.info("Initialized Agentic RAG")

    def _initialize_llm(self) -> AzureChatOpenAI:
        """Initialize LLM for agentic reasoning"""
        try:
            if config.azure_openai.api_key:
                return AzureChatOpenAI(
                    azure_endpoint=config.azure_openai.endpoint,
                    api_key=config.azure_openai.api_key,
                    api_version=config.azure_openai.api_version,
                    deployment_name=config.azure_openai.gpt4o_deployment,
                    temperature=0.3,
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
        )

    @trace_function("process_document")
    @track_agent("agentic_rag")
    def process_document(self, file_path: str) -> Dict[str, Any]:
        """Process a document with metadata extraction"""
        try:
            logger.info(f"Processing document", file_path=file_path)

            from pathlib import Path
            file_name = Path(file_path).name
            existing_metadata = self.storage.load_rag_metadata(file_name)

            if existing_metadata:
                logger.info(f"Document already processed: {file_name}")
                return {
                    "success": True,
                    "already_processed": True,
                    "file_path": file_path,
                }

            # Parse document
            parsed = self.parser.parse(file_path)
            content = parsed["content"]
            metadata = parsed["metadata"]

            # Chunk text
            chunks = self.parser.chunk_text(content, chunk_size=1000, chunk_overlap=200)

            logger.info(f"Parsed and chunked document", file_path=file_path, chunks=len(chunks))

            # Add to vector store with enhanced metadata
            chunk_ids = []
            chunk_metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = f"{file_name}_chunk_{i}"
                chunk_metadata = {
                    "file_name": file_name,
                    "file_path": file_path,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "file_type": metadata.get("extension"),
                    "file_size": metadata.get("file_size"),
                }
                chunk_ids.append(chunk_id)
                chunk_metadatas.append(chunk_metadata)

            self.vector_store.add_documents(
                texts=chunks,
                metadatas=chunk_metadatas,
                ids=chunk_ids,
            )

            self.vector_store.save()

            # Store metadata
            doc_metadata = {
                "file_name": file_name,
                "file_path": file_path,
                "num_chunks": len(chunks),
                "content_length": len(content),
                "processed": True,
                **metadata,
            }
            self.storage.save_rag_metadata(file_name, doc_metadata)

            logger.info(f"Successfully processed document", file_path=file_path, chunks=len(chunks))

            return {
                "success": True,
                "file_path": file_path,
                "num_chunks": len(chunks),
                "content_length": len(content),
            }

        except Exception as e:
            logger.error(f"Failed to process document: {e}", file_path=file_path)
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e),
            }

    @trace_function("contextualize_genie_output")
    @track_agent("agentic_rag_contextualize")
    def contextualize_genie_output(
        self,
        question: str,
        genie_result: Dict[str, Any],
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        AGENTIC METHOD: Analyze Genie output and find contextual documents.

        This is the key method that makes RAG truly agentic:
        1. Analyzes the SQL and data returned by Genie
        2. Understands what the data represents
        3. Generates smart queries to find relevant context
        4. Returns documents that explain the business meaning

        Args:
            question: Original user question
            genie_result: Results from Genie agent
            top_k: Number of contexts to retrieve

        Returns:
            Contextualized information with insights
        """
        try:
            # Step 1: Analyze Genie output using LLM
            sql_query = genie_result.get("sql_query", "")
            data = genie_result.get("data", [])
            columns = genie_result.get("columns", [])

            if not sql_query and not data:
                logger.info("No Genie output to contextualize")
                return {
                    "success": True,
                    "contexts": [],
                    "insights": "No data to contextualize",
                }

            # Step 2: Use LLM to understand what the data represents
            analysis_prompt = f"""Analyze this SQL query and data to understand what information it represents.

User Question: {question}

SQL Query: {sql_query}

Columns: {', '.join(columns)}

Sample Data: {str(data[:3]) if data else 'No data'}

Based on this, generate 3-5 specific search queries to find documents that would:
1. Explain the business context of these metrics/columns
2. Provide definitions or background information
3. Help interpret the results
4. Add relevant business insights

Return as JSON list of search queries:
{{"queries": ["query1", "query2", ...]}}
"""

            logger.info("Analyzing Genie output to generate contextual queries")

            response = self.llm.invoke(analysis_prompt)
            content = response.content

            # Parse response
            import json
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            try:
                parsed = json.loads(content)
                search_queries = parsed.get("queries", [])
            except:
                # Fallback: use original question
                search_queries = [question]

            logger.info(f"Generated {len(search_queries)} contextual search queries")

            # Step 3: Execute searches for each query
            all_contexts = []
            seen_chunks = set()

            for query in search_queries:
                results = self.vector_store.similarity_search(
                    query,
                    k=top_k,
                    score_threshold=0.7,
                )

                for doc, similarity in results:
                    chunk_id = doc.get("id")
                    if chunk_id not in seen_chunks:
                        seen_chunks.add(chunk_id)
                        all_contexts.append({
                            "text": doc["text"],
                            "similarity": similarity,
                            "file_name": doc["metadata"].get("file_name"),
                            "search_query": query,
                            "relevance": "business_context",
                        })

            # Step 4: Rank and filter contexts
            # Sort by similarity
            all_contexts.sort(key=lambda x: x["similarity"], reverse=True)
            top_contexts = all_contexts[:top_k]

            # Step 5: Generate insights about the contextualization
            if top_contexts:
                insight_prompt = f"""Based on the SQL results and these document contexts, provide a brief insight about what additional context was found.

SQL: {sql_query}
Data: {str(data[:2]) if data else 'No data'}

Contexts found: {len(top_contexts)} relevant documents

Provide a 1-2 sentence summary of what context was found and how it helps understand the data."""

                try:
                    insight_response = self.llm.invoke(insight_prompt)
                    insights = insight_response.content.strip()
                except:
                    insights = f"Found {len(top_contexts)} relevant documents to contextualize the data."
            else:
                insights = "No additional context found in documents."

            logger.info(
                f"Contextualized Genie output",
                contexts_found=len(top_contexts),
                queries_executed=len(search_queries),
            )

            return {
                "success": True,
                "contexts": top_contexts,
                "insights": insights,
                "search_queries_used": search_queries,
                "total_contexts_found": len(all_contexts),
            }

        except Exception as e:
            logger.error(f"Failed to contextualize Genie output: {e}")
            return {
                "success": False,
                "error": str(e),
                "contexts": [],
            }

    @trace_function("retrieve_context")
    def retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Basic retrieval for general queries (non-Genie).
        For Genie output, use contextualize_genie_output() instead.
        """
        try:
            results = self.vector_store.similarity_search(
                query,
                k=top_k,
                score_threshold=similarity_threshold,
            )

            contexts = []
            for doc, similarity in results:
                contexts.append({
                    "text": doc["text"],
                    "similarity": similarity,
                    "file_name": doc["metadata"].get("file_name"),
                    "chunk_index": doc["metadata"].get("chunk_index"),
                    "file_type": doc["metadata"].get("file_type"),
                })

            logger.info(f"Retrieved {len(contexts)} contexts", query_length=len(query))

            return contexts

        except Exception as e:
            logger.error(f"Failed to retrieve context: {e}")
            return []

    def start_monitoring(self):
        """Start monitoring directory for new files"""
        try:
            self.file_monitor = get_file_monitor(on_file_callback=self._on_new_file)
            self.file_monitor.process_existing_files()
            self.file_monitor.start()
            logger.info("Started file monitoring for Agentic RAG")
        except Exception as e:
            logger.error(f"Failed to start file monitoring: {e}")
            raise

    def stop_monitoring(self):
        """Stop file monitoring"""
        if self.file_monitor:
            self.file_monitor.stop()
            logger.info("Stopped file monitoring")

    def _on_new_file(self, file_path: str):
        """Callback when new file is detected"""
        logger.info(f"New file detected for RAG processing", file_path=file_path)
        try:
            result = self.process_document(file_path)
            if result["success"]:
                logger.info(f"Successfully processed new file", file_path=file_path)
            else:
                logger.error(f"Failed to process new file", file_path=file_path, error=result.get("error"))
        except Exception as e:
            logger.error(f"Error in file callback: {e}", file_path=file_path)

    def get_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics"""
        vector_stats = self.vector_store.get_stats()
        documents = self.list_documents()

        return {
            "total_documents": len(documents),
            "total_chunks": vector_stats.get("active_documents", 0),
            "vector_store_stats": vector_stats,
            "agentic_features": ["genie_contextualization", "intelligent_search", "insight_generation"],
        }

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all processed documents"""
        try:
            container_name = config.azure_storage.container_rag
            blob_names = self.storage.list_blobs(container_name, prefix="metadata/")

            documents = []
            for blob_name in blob_names:
                file_name = blob_name.replace("metadata/", "").replace(".json", "")
                metadata = self.storage.load_rag_metadata(file_name)
                if metadata:
                    documents.append(metadata)

            return documents
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []


# Global agentic RAG instance
_agentic_rag = None


def get_agentic_rag() -> AgenticRAG:
    """Get global agentic RAG instance"""
    global _agentic_rag
    if _agentic_rag is None:
        _agentic_rag = AgenticRAG()
    return _agentic_rag
