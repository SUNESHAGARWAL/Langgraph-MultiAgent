"""
FAISS Vector Store service for semantic search and similarity matching.
Persists to Azure Blob Storage for production use.
"""

import os
import io
import pickle
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import faiss
import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain.schema import Document

from src.core.config import config
from src.utils.embeddings import get_embedding_service
from src.utils.logging import get_logger, trace_function

logger = get_logger(__name__)


class FaissVectorStore:
    """
    FAISS-based vector store for semantic search.
    Supports multiple indices for different use cases (SQL caching, table understanding, RAG).

    IMPORTANT: Persists to Azure Blob Storage (not local disk) for production scalability.
    """

    def __init__(self, store_name: str):
        """
        Initialize vector store.

        Args:
            store_name: Name of the store (e.g., 'sql_cache', 'table_metadata', 'rag_docs')
        """
        self.store_name = store_name
        self.embedding_service = get_embedding_service()
        self.dimension = config.vector_store.dimension

        # Blob storage paths
        self.container_name = "vector-stores"
        self.blob_prefix = f"{store_name}/"
        self.index_blob_name = f"{self.blob_prefix}index.faiss"
        self.docs_blob_name = f"{self.blob_prefix}documents.pkl"

        # Local temp directory for FAISS operations (FAISS requires local files)
        self.temp_dir = Path(tempfile.gettempdir()) / "faiss_temp" / store_name
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.index: Optional[faiss.IndexFlatL2] = None
        self.documents: List[Dict[str, Any]] = []
        self.id_to_index: Dict[str, int] = {}

        # Get blob storage service
        self._storage = None

        self._load_or_create()

    @property
    def storage(self):
        """Lazy load blob storage to avoid circular imports"""
        if self._storage is None:
            from src.services.storage import get_blob_storage
            self._storage = get_blob_storage()
        return self._storage

    def _load_or_create(self):
        """Load existing index from Azure Blob Storage or create new one"""
        try:
            # Try to download from blob storage
            index_exists = self._download_from_blob()

            if index_exists:
                # Load from local temp files
                index_file = self.temp_dir / "index.faiss"
                docs_file = self.temp_dir / "documents.pkl"

                if index_file.exists() and docs_file.exists():
                    try:
                        self.index = faiss.read_index(str(index_file))
                        with open(docs_file, "rb") as f:
                            data = pickle.load(f)
                            self.documents = data["documents"]
                            self.id_to_index = data["id_to_index"]

                        logger.info(
                            f"Loaded {self.store_name} vector store from Azure Blob Storage",
                            num_documents=len(self.documents),
                        )
                        return
                    except Exception as e:
                        logger.warning(f"Failed to load index from blob, creating new: {e}")

            # Create new index if loading failed
            self._create_new_index()

        except Exception as e:
            logger.warning(f"Could not access blob storage, creating new index: {e}")
            self._create_new_index()

    def _download_from_blob(self) -> bool:
        """
        Download vector store files from Azure Blob Storage to temp directory.

        Returns:
            True if files were downloaded successfully, False otherwise
        """
        try:
            # Download index file
            index_data = self.storage.download_blob(self.container_name, self.index_blob_name)
            if index_data:
                index_file = self.temp_dir / "index.faiss"
                with open(index_file, "wb") as f:
                    f.write(index_data)
                logger.debug(f"Downloaded index for {self.store_name} from blob storage")
            else:
                return False

            # Download documents file
            docs_data = self.storage.download_blob(self.container_name, self.docs_blob_name)
            if docs_data:
                docs_file = self.temp_dir / "documents.pkl"
                with open(docs_file, "wb") as f:
                    f.write(docs_data)
                logger.debug(f"Downloaded documents for {self.store_name} from blob storage")
                return True
            else:
                return False

        except Exception as e:
            logger.debug(f"Could not download from blob storage: {e}")
            return False

    def _create_new_index(self):
        """Create a new FAISS index"""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents = []
        self.id_to_index = {}
        logger.info(f"Created new {self.store_name} vector store")

    @trace_function("add_documents")
    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Add documents to the vector store.

        Args:
            texts: List of texts to add
            metadatas: Optional metadata for each text
            ids: Optional IDs for each text (auto-generated if not provided)

        Returns:
            List of document IDs
        """
        if not texts:
            return []

        # Generate embeddings
        embeddings = self.embedding_service.generate_embeddings_batch(texts)

        # Generate IDs if not provided
        if ids is None:
            ids = [f"{self.store_name}_{len(self.documents) + i}" for i in range(len(texts))]

        if metadatas is None:
            metadatas = [{} for _ in texts]

        # Add to FAISS index
        embeddings_array = np.array(embeddings).astype("float32")
        start_idx = len(self.documents)
        self.index.add(embeddings_array)

        # Store documents
        for i, (text, metadata, doc_id) in enumerate(zip(texts, metadatas, ids)):
            doc = {
                "id": doc_id,
                "text": text,
                "metadata": metadata,
                "embedding": embeddings[i],
            }
            self.documents.append(doc)
            self.id_to_index[doc_id] = start_idx + i

        logger.info(
            f"Added {len(texts)} documents to {self.store_name}",
            total_documents=len(self.documents),
        )

        return ids

    @trace_function("similarity_search")
    def similarity_search(
        self,
        query: str,
        k: int = None,
        score_threshold: Optional[float] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for similar documents.

        Args:
            query: Query text
            k: Number of results to return
            score_threshold: Optional minimum similarity score (lower is more similar for L2)

        Returns:
            List of (document, similarity_score) tuples
        """
        if k is None:
            k = config.vector_store.similarity_top_k

        if len(self.documents) == 0:
            return []

        # Generate query embedding
        query_embedding = self.embedding_service.generate_embedding(query)
        query_array = np.array([query_embedding]).astype("float32")

        # Search
        k = min(k, len(self.documents))
        distances, indices = self.index.search(query_array, k)

        results = []
        for distance, idx in zip(distances[0], indices[0]):
            if idx < len(self.documents):
                # Convert L2 distance to similarity score (lower distance = higher similarity)
                similarity = 1 / (1 + distance)

                if score_threshold is None or similarity >= score_threshold:
                    results.append((self.documents[idx], similarity))

        logger.debug(
            f"Similarity search returned {len(results)} results",
            query_length=len(query),
        )

        return results

    @trace_function("get_by_id")
    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        idx = self.id_to_index.get(doc_id)
        if idx is not None and idx < len(self.documents):
            return self.documents[idx]
        return None

    @trace_function("delete_by_id")
    def delete_by_id(self, doc_id: str) -> bool:
        """
        Delete document by ID.
        Note: This marks as deleted but doesn't remove from index (FAISS limitation).
        """
        idx = self.id_to_index.get(doc_id)
        if idx is not None and idx < len(self.documents):
            self.documents[idx]["deleted"] = True
            logger.info(f"Marked document {doc_id} as deleted")
            return True
        return False

    def save(self):
        """
        Persist index to Azure Blob Storage.

        Process:
        1. Write FAISS index and documents to temp directory
        2. Upload to Azure Blob Storage
        3. Clean up temp files
        """
        try:
            # Ensure temp directory exists
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # Write to temp files (FAISS requires local files)
            index_file = self.temp_dir / "index.faiss"
            docs_file = self.temp_dir / "documents.pkl"

            faiss.write_index(self.index, str(index_file))

            with open(docs_file, "wb") as f:
                pickle.dump(
                    {
                        "documents": self.documents,
                        "id_to_index": self.id_to_index,
                    },
                    f,
                )

            # Upload to Azure Blob Storage
            with open(index_file, "rb") as f:
                index_data = f.read()
                self.storage.upload_blob(
                    self.container_name,
                    self.index_blob_name,
                    index_data
                )

            with open(docs_file, "rb") as f:
                docs_data = f.read()
                self.storage.upload_blob(
                    self.container_name,
                    self.docs_blob_name,
                    docs_data
                )

            logger.info(
                f"Saved {self.store_name} vector store to Azure Blob Storage",
                container=self.container_name,
                num_documents=len(self.documents)
            )

        except Exception as e:
            logger.error(f"Failed to save vector store to blob storage: {e}")
            raise

    def clear(self):
        """Clear all data"""
        self._create_new_index()
        logger.info(f"Cleared {self.store_name} vector store")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store"""
        active_docs = [d for d in self.documents if not d.get("deleted", False)]

        return {
            "store_name": self.store_name,
            "total_documents": len(self.documents),
            "active_documents": len(active_docs),
            "index_size": self.index.ntotal if self.index else 0,
            "dimension": self.dimension,
            "storage_location": "Azure Blob Storage",
            "container": self.container_name,
        }


class VectorStoreManager:
    """
    Manager for multiple vector stores.
    """

    def __init__(self):
        self.stores: Dict[str, FaissVectorStore] = {}

    def get_store(self, store_name: str) -> FaissVectorStore:
        """Get or create a vector store"""
        if store_name not in self.stores:
            self.stores[store_name] = FaissVectorStore(store_name)
        return self.stores[store_name]

    def save_all(self):
        """Save all vector stores to Azure Blob Storage"""
        for store in self.stores.values():
            store.save()
        logger.info("Saved all vector stores to Azure Blob Storage")

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all vector stores"""
        return {name: store.get_stats() for name, store in self.stores.items()}


# Global vector store manager
_vector_store_manager = None


def get_vector_store_manager() -> VectorStoreManager:
    """Get global vector store manager"""
    global _vector_store_manager
    if _vector_store_manager is None:
        _vector_store_manager = VectorStoreManager()
    return _vector_store_manager


def get_vector_store(store_name: str) -> FaissVectorStore:
    """Get a specific vector store"""
    return get_vector_store_manager().get_store(store_name)
