"""
Smart caching layer with semantic similarity using Redis (if available) or file-based FAISS.
Supports SQL query caching and response caching with vector similarity matching.
"""

import json
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta

try:
    import redis
    from redisvl.index import SearchIndex
    from redisvl.query import VectorQuery
    from redisvl.query.filter import Tag

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger_import = __import__("src.utils.logging", fromlist=["get_logger"])
    logger_import.get_logger(__name__).warning(
        "Redis not available, falling back to FAISS-based caching"
    )

from src.core.config import config
from src.services.vector_store import get_vector_store
from src.utils.embeddings import get_embedding_service
from src.utils.logging import get_logger, trace_function

logger = get_logger(__name__)


class SmartCache:
    """
    Smart caching with semantic similarity.
    Falls back to FAISS if Redis is not available.
    """

    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.use_redis = config.redis.enabled and REDIS_AVAILABLE

        if self.use_redis:
            self._init_redis()
        else:
            self._init_faiss()

        logger.info(
            f"Initialized SmartCache",
            backend="redis" if self.use_redis else "faiss",
        )

    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=config.redis.host,
                port=config.redis.port,
                password=config.redis.password,
                db=config.redis.db,
                decode_responses=False,
            )
            self.redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis, falling back to FAISS: {e}")
            self.use_redis = False
            self._init_faiss()

    def _init_faiss(self):
        """Initialize FAISS-based cache"""
        self.cache_store = get_vector_store("smart_cache")
        self.cache_metadata = {}

    @trace_function("cache_set")
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """
        Set a cache entry with optional TTL and tags.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = use config default)
            tags: Optional tags for categorization

        Returns:
            True if successful
        """
        if ttl is None:
            ttl = config.cache.ttl_seconds

        cache_entry = {
            "key": key,
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
            "ttl": ttl,
            "tags": tags or [],
        }

        try:
            if self.use_redis:
                return self._redis_set(key, cache_entry, ttl)
            else:
                return self._faiss_set(key, cache_entry, ttl)
        except Exception as e:
            logger.error(f"Failed to set cache: {e}", key=key)
            return False

    @trace_function("cache_get")
    def get(self, key: str) -> Optional[Any]:
        """
        Get exact cache entry by key.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        try:
            if self.use_redis:
                return self._redis_get(key)
            else:
                return self._faiss_get(key)
        except Exception as e:
            logger.error(f"Failed to get cache: {e}", key=key)
            return None

    @trace_function("cache_search_similar")
    def search_similar(
        self,
        query: str,
        similarity_threshold: Optional[float] = None,
        top_k: int = 1,
        tags: Optional[List[str]] = None,
    ) -> List[Tuple[str, Any, float]]:
        """
        Search for similar cached entries using semantic similarity.

        Args:
            query: Query text
            similarity_threshold: Minimum similarity score (None = use config)
            top_k: Number of results to return
            tags: Optional tags to filter by

        Returns:
            List of (key, value, similarity_score) tuples
        """
        if similarity_threshold is None:
            similarity_threshold = config.cache.similarity_threshold

        try:
            if self.use_redis:
                return self._redis_search_similar(query, similarity_threshold, top_k, tags)
            else:
                return self._faiss_search_similar(query, similarity_threshold, top_k, tags)
        except Exception as e:
            logger.error(f"Failed to search similar cache entries: {e}")
            return []

    @trace_function("cache_delete")
    def delete(self, key: str) -> bool:
        """Delete cache entry"""
        try:
            if self.use_redis:
                return self._redis_delete(key)
            else:
                return self._faiss_delete(key)
        except Exception as e:
            logger.error(f"Failed to delete cache: {e}", key=key)
            return False

    # Redis implementation methods

    def _redis_set(self, key: str, cache_entry: dict, ttl: int) -> bool:
        """Set cache in Redis"""
        cache_key = f"cache:{key}"
        serialized = json.dumps(cache_entry)
        self.redis_client.setex(cache_key, ttl, serialized)

        # Store embedding for similarity search
        embedding = self.embedding_service.generate_embedding(key)
        embedding_key = f"embedding:{key}"
        self.redis_client.setex(
            embedding_key,
            ttl,
            json.dumps(embedding),
        )

        logger.debug(f"Set Redis cache: {key}")
        return True

    def _redis_get(self, key: str) -> Optional[Any]:
        """Get cache from Redis"""
        cache_key = f"cache:{key}"
        data = self.redis_client.get(cache_key)

        if data:
            cache_entry = json.loads(data)
            logger.debug(f"Redis cache hit: {key}")
            return cache_entry["value"]

        logger.debug(f"Redis cache miss: {key}")
        return None

    def _redis_search_similar(
        self,
        query: str,
        similarity_threshold: float,
        top_k: int,
        tags: Optional[List[str]],
    ) -> List[Tuple[str, Any, float]]:
        """Search similar in Redis using vector similarity"""
        # For simplicity, scan all keys and compute similarity
        # In production, use RedisVL's SearchIndex for better performance

        query_embedding = self.embedding_service.generate_embedding(query)
        results = []

        # Scan all cache keys
        for key in self.redis_client.scan_iter("cache:*"):
            key_str = key.decode("utf-8").replace("cache:", "")
            embedding_key = f"embedding:{key_str}"

            embedding_data = self.redis_client.get(embedding_key)
            if not embedding_data:
                continue

            embedding = json.loads(embedding_data)

            # Compute cosine similarity
            similarity = self._cosine_similarity(query_embedding, embedding)

            if similarity >= similarity_threshold:
                cache_data = self.redis_client.get(key)
                if cache_data:
                    cache_entry = json.loads(cache_data)

                    # Filter by tags if provided
                    if tags:
                        entry_tags = cache_entry.get("tags", [])
                        if not any(tag in entry_tags for tag in tags):
                            continue

                    results.append((key_str, cache_entry["value"], similarity))

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:top_k]

    def _redis_delete(self, key: str) -> bool:
        """Delete from Redis"""
        cache_key = f"cache:{key}"
        embedding_key = f"embedding:{key}"

        self.redis_client.delete(cache_key)
        self.redis_client.delete(embedding_key)

        logger.debug(f"Deleted Redis cache: {key}")
        return True

    # FAISS implementation methods

    def _faiss_set(self, key: str, cache_entry: dict, ttl: int) -> bool:
        """Set cache in FAISS"""
        # Calculate expiry time
        expiry = datetime.utcnow() + timedelta(seconds=ttl)

        # Store in vector store
        metadata = {
            "value": json.dumps(cache_entry["value"]),
            "timestamp": cache_entry["timestamp"],
            "expiry": expiry.isoformat(),
            "tags": cache_entry["tags"],
        }

        self.cache_store.add_documents(
            texts=[key],
            metadatas=[metadata],
            ids=[key],
        )

        # Store in metadata dict for quick lookup
        self.cache_metadata[key] = cache_entry

        logger.debug(f"Set FAISS cache: {key}")
        return True

    def _faiss_get(self, key: str) -> Optional[Any]:
        """Get cache from FAISS"""
        if key in self.cache_metadata:
            cache_entry = self.cache_metadata[key]

            # Check expiry
            expiry_str = cache_entry.get("expiry")
            if expiry_str:
                expiry = datetime.fromisoformat(expiry_str)
                if datetime.utcnow() > expiry:
                    del self.cache_metadata[key]
                    logger.debug(f"FAISS cache expired: {key}")
                    return None

            logger.debug(f"FAISS cache hit: {key}")
            return cache_entry["value"]

        logger.debug(f"FAISS cache miss: {key}")
        return None

    def _faiss_search_similar(
        self,
        query: str,
        similarity_threshold: float,
        top_k: int,
        tags: Optional[List[str]],
    ) -> List[Tuple[str, Any, float]]:
        """Search similar in FAISS"""
        results = self.cache_store.similarity_search(
            query,
            k=top_k * 2,  # Get more to account for filtering
            score_threshold=similarity_threshold,
        )

        filtered_results = []

        for doc, similarity in results:
            key = doc["text"]

            # Check if expired
            expiry_str = doc["metadata"].get("expiry")
            if expiry_str:
                expiry = datetime.fromisoformat(expiry_str)
                if datetime.utcnow() > expiry:
                    continue

            # Filter by tags
            if tags:
                doc_tags = doc["metadata"].get("tags", [])
                if not any(tag in doc_tags for tag in tags):
                    continue

            # Deserialize value
            value = json.loads(doc["metadata"]["value"])

            filtered_results.append((key, value, similarity))

            if len(filtered_results) >= top_k:
                break

        return filtered_results

    def _faiss_delete(self, key: str) -> bool:
        """Delete from FAISS"""
        self.cache_store.delete_by_id(key)

        if key in self.cache_metadata:
            del self.cache_metadata[key]

        logger.debug(f"Deleted FAISS cache: {key}")
        return True

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors"""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if self.use_redis:
            info = self.redis_client.info("keyspace")
            return {
                "backend": "redis",
                "keyspace": info,
            }
        else:
            return {
                "backend": "faiss",
                "stats": self.cache_store.get_stats(),
                "metadata_entries": len(self.cache_metadata),
            }


# Global cache instance
_smart_cache = None


def get_smart_cache() -> SmartCache:
    """Get global smart cache instance"""
    global _smart_cache
    if _smart_cache is None:
        _smart_cache = SmartCache()
    return _smart_cache
