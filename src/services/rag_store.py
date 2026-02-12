"""
RAG Vector Store with FAISS

Provides document storage and semantic search for RAG.

Features:
- FAISS vector indexing
- Document ingestion with chunking
- Semantic search
- Incremental updates
- Persistence to disk
"""

import os
import pickle
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np

from src.utils.embeddings import EmbeddingService
from src.utils.parsers import Document, DocumentParser

logger = logging.getLogger(__name__)


class RAGStore:
    """
    Vector store for RAG documents using FAISS

    Stores document embeddings and enables semantic search.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store_path: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize RAG store

        Args:
            embedding_service: Service for generating embeddings
            vector_store_path: Path to store FAISS index
            chunk_size: Size of document chunks
            chunk_overlap: Overlap between chunks
        """
        self.embeddings = embedding_service
        self.vector_store_path = Path(vector_store_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Document storage
        self.documents: List[Document] = []
        self.index = None

        # Lazy import FAISS
        try:
            import faiss
            self.faiss = faiss
            self.has_faiss = True
        except ImportError:
            logger.warning("faiss-cpu not installed - RAG functionality disabled")
            self.has_faiss = False
            return

        # Load existing index if available
        self._load_index()

        logger.info(f"✓ RAG store initialized (path: {vector_store_path})")

    def _load_index(self):
        """Load FAISS index from disk"""
        if not self.has_faiss:
            return

        index_file = self.vector_store_path / "faiss.index"
        docs_file = self.vector_store_path / "documents.pkl"

        if index_file.exists() and docs_file.exists():
            try:
                # Load FAISS index
                self.index = self.faiss.read_index(str(index_file))

                # Load documents
                with open(docs_file, 'rb') as f:
                    self.documents = pickle.load(f)

                logger.info(f"✓ Loaded RAG index with {len(self.documents)} documents")

            except Exception as e:
                logger.error(f"Failed to load RAG index: {e}")
                self.index = None
                self.documents = []
        else:
            logger.info("No existing RAG index found - starting fresh")

    def _save_index(self):
        """Save FAISS index to disk"""
        if not self.has_faiss or self.index is None:
            return

        # Create directory if needed
        self.vector_store_path.mkdir(parents=True, exist_ok=True)

        index_file = self.vector_store_path / "faiss.index"
        docs_file = self.vector_store_path / "documents.pkl"

        try:
            # Save FAISS index
            self.faiss.write_index(self.index, str(index_file))

            # Save documents
            with open(docs_file, 'wb') as f:
                pickle.dump(self.documents, f)

            logger.info(f"✓ Saved RAG index with {len(self.documents)} documents")

        except Exception as e:
            logger.error(f"Failed to save RAG index: {e}", exc_info=True)

    def add_documents(self, documents: List[Document], save: bool = True):
        """
        Add documents to RAG store

        Args:
            documents: List of documents to add
            save: Save index to disk after adding
        """
        if not self.has_faiss:
            logger.warning("FAISS not available - cannot add documents")
            return

        if not documents:
            return

        logger.info(f"Adding {len(documents)} documents to RAG store...")

        # Chunk all documents
        chunks = []
        for doc in documents:
            doc_chunks = DocumentParser.chunk_text(
                doc.content,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )

            # Create document for each chunk
            for i, chunk in enumerate(doc_chunks):
                chunk_doc = Document(
                    content=chunk,
                    metadata={
                        **doc.metadata,
                        "chunk_index": i,
                        "total_chunks": len(doc_chunks)
                    }
                )
                chunks.append(chunk_doc)

        logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")

        # Generate embeddings (batched)
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embeddings.generate_embeddings_batch(texts)

        # Add embeddings to documents
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        # Add to FAISS index
        embeddings_array = np.array(embeddings).astype('float32')

        if self.index is None:
            # Create new index
            dimension = len(embeddings[0])
            self.index = self.faiss.IndexFlatL2(dimension)
            logger.info(f"Created new FAISS index (dimension: {dimension})")

        # Add vectors
        self.index.add(embeddings_array)
        self.documents.extend(chunks)

        logger.info(f"✓ Added {len(chunks)} chunks to RAG store (total: {len(self.documents)})")

        # Save to disk
        if save:
            self._save_index()

    def search(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.7
    ) -> List[Document]:
        """
        Search for relevant documents

        Args:
            query: Search query
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity threshold

        Returns:
            List of relevant documents (sorted by similarity)
        """
        if not self.has_faiss or self.index is None or len(self.documents) == 0:
            logger.warning("No RAG index available")
            return []

        # Generate query embedding
        query_embedding = self.embeddings.generate_embedding(query)
        query_vector = np.array([query_embedding]).astype('float32')

        # Search FAISS index
        distances, indices = self.index.search(query_vector, min(top_k, len(self.documents)))

        # Convert L2 distances to cosine similarity (approximate)
        # Assuming normalized vectors: cosine_sim ≈ 1 - (L2_dist^2 / 2)
        similarities = 1.0 - (distances[0] ** 2 / 2.0)

        # Filter by minimum similarity and return documents
        results = []
        for idx, similarity in zip(indices[0], similarities):
            if similarity >= min_similarity:
                doc = self.documents[idx]
                # Add similarity to metadata (without modifying original)
                result_doc = Document(
                    content=doc.content,
                    metadata={**doc.metadata, "similarity": float(similarity)},
                    embedding=doc.embedding
                )
                results.append(result_doc)

        logger.info(f"RAG search: {len(results)} documents found (query: '{query[:50]}...')")

        return results

    def clear(self):
        """Clear all documents from store"""
        self.documents = []
        self.index = None
        logger.info("RAG store cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get RAG store statistics"""
        return {
            "total_documents": len(self.documents),
            "has_index": self.index is not None,
            "has_faiss": self.has_faiss,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "index_path": str(self.vector_store_path)
        }


# Global singleton instance
_rag_store: Optional[RAGStore] = None


def get_rag_store() -> Optional[RAGStore]:
    """Get global RAG store instance (may be None if not initialized)"""
    return _rag_store


def initialize_rag_store(
    embedding_service: EmbeddingService,
    vector_store_path: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> RAGStore:
    """
    Initialize global RAG store

    Args:
        embedding_service: Embedding service instance
        vector_store_path: Path to store FAISS index
        chunk_size: Size of document chunks
        chunk_overlap: Overlap between chunks

    Returns:
        Initialized RAGStore instance
    """
    global _rag_store
    _rag_store = RAGStore(
        embedding_service=embedding_service,
        vector_store_path=vector_store_path,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    return _rag_store
