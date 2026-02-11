"""
Semantic caching for Genie queries using FAISS vector similarity.

Caches SQL query results based on semantic similarity of questions,
reducing costs and latency for similar queries.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from langchain_core.documents import Document

from src.utils.logging import get_logger

logger = get_logger(__name__)


class GenieCache:
    """Semantic cache for Genie SQL queries."""

    def __init__(
        self,
        embeddings: AzureOpenAIEmbeddings,
        similarity_threshold: float = 0.90,
        cache_dir: str = "./data/cache",
        ttl_hours: int = 24,
    ):
        """
        Initialize Genie cache.

        Args:
            embeddings: Embedding model for semantic similarity
            similarity_threshold: Minimum similarity score for cache hit (0-1)
            cache_dir: Directory to persist cache
            ttl_hours: Time-to-live for cache entries in hours
        """
        self.embeddings = embeddings
        self.similarity_threshold = similarity_threshold
        self.cache_dir = Path(cache_dir)
        self.ttl_hours = ttl_hours

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Vector store for semantic search
        self.vectorstore: Optional[FAISS] = None

        # Metadata store: query_hash -> {result, timestamp, question}
        self.metadata: Dict[str, Dict[str, Any]] = {}

        # Stats
        self.stats = {
            "hits": 0,
            "misses": 0,
            "stores": 0,
            "evictions": 0,
        }

        # Load existing cache
        self._load_cache()

        logger.info(
            f"Initialized GenieCache with threshold={similarity_threshold}, "
            f"ttl={ttl_hours}h, cache_dir={cache_dir}"
        )

    def _query_hash(self, question: str) -> str:
        """Generate hash for question."""
        return hashlib.md5(question.encode()).hexdigest()

    def _is_expired(self, timestamp: str) -> bool:
        """Check if cache entry is expired."""
        try:
            entry_time = datetime.fromisoformat(timestamp)
            expiry_time = entry_time + timedelta(hours=self.ttl_hours)
            return datetime.now() > expiry_time
        except Exception:
            return True

    def _load_cache(self):
        """Load cache from disk."""
        vector_path = self.cache_dir / "vectorstore"
        metadata_path = self.cache_dir / "metadata.json"

        try:
            if vector_path.exists():
                self.vectorstore = FAISS.load_local(
                    str(vector_path),
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info(f"Loaded vector store from {vector_path}")

            if metadata_path.exists():
                with open(metadata_path, "r") as f:
                    self.metadata = json.load(f)

                # Clean expired entries
                self._clean_expired()

                logger.info(f"Loaded {len(self.metadata)} cache entries from {metadata_path}")

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            self.vectorstore = None
            self.metadata = {}

    def _save_cache(self):
        """Save cache to disk."""
        try:
            if self.vectorstore:
                vector_path = self.cache_dir / "vectorstore"
                self.vectorstore.save_local(str(vector_path))

            metadata_path = self.cache_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(self.metadata, f, indent=2)

            logger.debug("Saved cache to disk")

        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _clean_expired(self):
        """Remove expired cache entries."""
        expired_hashes = [
            query_hash
            for query_hash, meta in self.metadata.items()
            if self._is_expired(meta.get("timestamp", ""))
        ]

        for query_hash in expired_hashes:
            del self.metadata[query_hash]
            self.stats["evictions"] += 1

        if expired_hashes:
            logger.info(f"Evicted {len(expired_hashes)} expired cache entries")

    def get(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Get cached result for similar question.

        Args:
            question: Natural language question

        Returns:
            Cached result dict if similar query found, None otherwise
        """
        if not self.vectorstore or not self.metadata:
            self.stats["misses"] += 1
            return None

        try:
            # Semantic search for similar questions
            results = self.vectorstore.similarity_search_with_score(
                question,
                k=1
            )

            if not results:
                self.stats["misses"] += 1
                return None

            doc, score = results[0]

            # Convert distance to similarity (FAISS returns L2 distance)
            # Lower distance = higher similarity
            # Normalize to 0-1 range where 1 is perfect match
            similarity = 1 / (1 + score)

            logger.debug(f"Cache search - Question: '{question}', Similarity: {similarity:.3f}")

            # Check similarity threshold
            if similarity >= self.similarity_threshold:
                query_hash = doc.metadata.get("query_hash")

                if query_hash in self.metadata:
                    cached_entry = self.metadata[query_hash]

                    # Check if expired
                    if self._is_expired(cached_entry.get("timestamp", "")):
                        logger.debug(f"Cache entry expired for: {question}")
                        del self.metadata[query_hash]
                        self.stats["misses"] += 1
                        self.stats["evictions"] += 1
                        return None

                    # Cache HIT
                    self.stats["hits"] += 1
                    cached_question = cached_entry.get("question", "")

                    logger.info(
                        f"✓ Cache HIT (similarity: {similarity:.3f})\n"
                        f"  Original: '{cached_question}'\n"
                        f"  Current:  '{question}'"
                    )

                    return cached_entry.get("result")

            # Cache MISS
            self.stats["misses"] += 1
            logger.debug(f"Cache MISS - Similarity {similarity:.3f} below threshold {self.similarity_threshold}")
            return None

        except Exception as e:
            logger.error(f"Cache lookup failed: {e}")
            self.stats["misses"] += 1
            return None

    def set(self, question: str, result: Dict[str, Any]):
        """
        Cache query result.

        Args:
            question: Natural language question
            result: Query result to cache
        """
        try:
            query_hash = self._query_hash(question)

            # Store metadata
            self.metadata[query_hash] = {
                "question": question,
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "query_hash": query_hash,
            }

            # Add to vector store
            doc = Document(
                page_content=question,
                metadata={"query_hash": query_hash}
            )

            if self.vectorstore is None:
                self.vectorstore = FAISS.from_documents([doc], self.embeddings)
            else:
                self.vectorstore.add_documents([doc])

            self.stats["stores"] += 1

            logger.info(f"✓ Cached result for: {question}")

            # Persist to disk
            self._save_cache()

        except Exception as e:
            logger.error(f"Cache store failed: {e}")

    def clear(self):
        """Clear all cache entries."""
        self.vectorstore = None
        self.metadata = {}

        # Remove cache files
        try:
            import shutil
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0

        return {
            **self.stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "cache_size": len(self.metadata),
        }

    def __del__(self):
        """Save cache on destruction."""
        try:
            self._save_cache()
        except Exception:
            pass


def get_cache(
    embeddings: AzureOpenAIEmbeddings,
    similarity_threshold: float = 0.90,
    cache_dir: str = "./data/cache",
    ttl_hours: int = 24,
) -> GenieCache:
    """
    Get or create Genie cache instance.

    Args:
        embeddings: Embedding model
        similarity_threshold: Minimum similarity for cache hit
        cache_dir: Cache persistence directory
        ttl_hours: Cache entry TTL in hours

    Returns:
        GenieCache instance
    """
    return GenieCache(
        embeddings=embeddings,
        similarity_threshold=similarity_threshold,
        cache_dir=cache_dir,
        ttl_hours=ttl_hours,
    )
