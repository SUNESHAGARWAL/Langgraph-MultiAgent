"""
RAG (Retrieval-Augmented Generation) Agent for document processing and retrieval.
Monitors files, processes them, and provides context for user queries.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path

from src.services.vector_store import get_vector_store
from src.services.file_monitor import get_file_monitor
from src.services.storage import get_storage_service
from src.utils.parsers import get_document_parser
from src.utils.logging import get_logger, trace_function
from src.services.mlflow_tracker import track_agent

logger = get_logger(__name__)


class RAGAgent:
    """
    Agentic RAG system that:
    1. Monitors a directory for new documents
    2. Processes documents (PDF, DOCX, CSV, etc.)
    3. Chunks and embeds content
    4. Stores in vector store
    5. Retrieves relevant context for queries
    """

    def __init__(self):
        self.vector_store = get_vector_store("rag_documents")
        self.storage = get_storage_service()
        self.parser = get_document_parser()
        self.file_monitor = None  # Initialized when start_monitoring is called

        logger.info("Initialized RAGAgent")

    @trace_function("process_document")
    @track_agent("rag_agent")
    def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Process a document: parse, chunk, embed, and store.

        Args:
            file_path: Path to the document

        Returns:
            Processing results
        """
        try:
            logger.info(f"Processing document", file_path=file_path)

            # Check if already processed
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
            chunks = self.parser.chunk_text(
                content,
                chunk_size=1000,
                chunk_overlap=200,
            )

            logger.info(
                f"Parsed and chunked document",
                file_path=file_path,
                chunks=len(chunks),
            )

            # Add to vector store
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

            # Save vector store
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

            logger.info(
                f"Successfully processed document",
                file_path=file_path,
                chunks=len(chunks),
            )

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

    @trace_function("retrieve_context")
    def retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant document chunks for a query.

        Args:
            query: User query
            top_k: Number of chunks to retrieve
            similarity_threshold: Minimum similarity score

        Returns:
            List of relevant chunks with metadata
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

            logger.info(
                f"Retrieved {len(contexts)} relevant contexts",
                query_length=len(query),
            )

            return contexts

        except Exception as e:
            logger.error(f"Failed to retrieve context: {e}")
            return []

    def start_monitoring(self):
        """Start monitoring directory for new files"""
        try:
            # Initialize file monitor with callback
            self.file_monitor = get_file_monitor(
                on_file_callback=self._on_new_file,
            )

            # Process existing files first
            self.file_monitor.process_existing_files()

            # Start monitoring
            self.file_monitor.start()

            logger.info("Started file monitoring for RAG")

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
                logger.error(
                    f"Failed to process new file",
                    file_path=file_path,
                    error=result.get("error"),
                )

        except Exception as e:
            logger.error(f"Error in file callback: {e}", file_path=file_path)

    @trace_function("get_document_summary")
    def get_document_summary(self, file_name: str) -> Optional[Dict[str, Any]]:
        """Get summary of a processed document"""
        return self.storage.load_rag_metadata(file_name)

    @trace_function("list_documents")
    def list_documents(self) -> List[Dict[str, Any]]:
        """List all processed documents"""
        try:
            blob_names = self.storage.list_blobs(
                self.storage.blob_service_client.get_container_client(
                    self.storage.container_rag
                ).container_name,
                prefix="metadata/",
            )

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

    @trace_function("search_documents")
    def search_documents(
        self,
        query: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search for documents relevant to a query.

        Args:
            query: Search query
            top_k: Number of documents to return

        Returns:
            List of relevant documents with snippets
        """
        # Get relevant chunks
        chunks = self.retrieve_context(query, top_k=top_k * 3)

        # Group by document
        doc_chunks = {}
        for chunk in chunks:
            file_name = chunk["file_name"]
            if file_name not in doc_chunks:
                doc_chunks[file_name] = []
            doc_chunks[file_name].append(chunk)

        # Create document summaries
        documents = []
        for file_name, chunks_list in list(doc_chunks.items())[:top_k]:
            metadata = self.storage.load_rag_metadata(file_name)

            # Get best snippet (highest similarity)
            best_chunk = max(chunks_list, key=lambda x: x["similarity"])

            documents.append({
                "file_name": file_name,
                "file_type": metadata.get("file_type") if metadata else None,
                "snippet": best_chunk["text"][:200] + "...",
                "similarity": best_chunk["similarity"],
                "num_relevant_chunks": len(chunks_list),
            })

        return documents

    def get_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics"""
        vector_stats = self.vector_store.get_stats()
        documents = self.list_documents()

        return {
            "total_documents": len(documents),
            "total_chunks": vector_stats.get("active_documents", 0),
            "vector_store_stats": vector_stats,
        }


# Global RAG agent
_rag_agent = None


def get_rag_agent() -> RAGAgent:
    """Get global RAG agent"""
    global _rag_agent
    if _rag_agent is None:
        _rag_agent = RAGAgent()
    return _rag_agent
