"""
Smart SQL Cache with Semantic Similarity

Caches Genie SQL query results with semantic similarity matching.
Avoids redundant API calls for similar queries.

Features:
- Semantic similarity matching (cosine similarity)
- TTL-based expiration
- Automatic cache pruning
- Cache statistics
- In-memory storage (upgradable to Redis)
"""

import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from src.utils.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with result and metadata"""
    query: str
    result: str
    embedding: List[float]
    timestamp: float
    hit_count: int = 0


class SmartSQLCache:
    """
    Semantic cache for SQL query results

    Uses embedding similarity to match semantically similar queries.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        ttl_seconds: int = 3600,
        similarity_threshold: float = 0.90,
        max_entries: int = 1000
    ):
        """
        Initialize smart cache

        Args:
            embedding_service: Service for generating embeddings
            ttl_seconds: Time-to-live for cache entries (seconds)
            similarity_threshold: Minimum similarity for cache hit (0-1)
            max_entries: Maximum cache entries (LRU eviction)
        """
        self.embeddings = embedding_service
        self.ttl = ttl_seconds
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries

        # Cache storage: {cache_key: CacheEntry}
        self._cache: Dict[str, CacheEntry] = {}

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        logger.info(f"✓ Smart SQL cache initialized "
                   f"(TTL: {ttl_seconds}s, threshold: {similarity_threshold}, "
                   f"max: {max_entries} entries)")

    def get(self, query: str) -> Optional[str]:
        """
        Get cached result for query (with semantic similarity matching)

        Args:
            query: SQL query to lookup

        Returns:
            Cached result if similar query found, None otherwise
        """
        if not query or not query.strip():
            return None

        # Generate query embedding
        query_embedding = self.embeddings.generate_embedding(query)

        # Search for similar cached query
        best_match = None
        best_similarity = 0.0

        current_time = time.time()

        for cache_key, entry in list(self._cache.items()):
            # Check if entry expired
            if current_time - entry.timestamp > self.ttl:
                del self._cache[cache_key]
                continue

            # Calculate similarity
            similarity = self.embeddings.cosine_similarity(query_embedding, entry.embedding)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = entry

        # Check if best match exceeds threshold
        if best_match and best_similarity >= self.similarity_threshold:
            self._hits += 1
            best_match.hit_count += 1

            logger.info(f"✓ Cache HIT (similarity: {best_similarity:.3f}, "
                       f"query: '{query[:50]}...', "
                       f"hit_count: {best_match.hit_count})")

            return best_match.result
        else:
            self._misses += 1

            if best_match:
                logger.info(f"✗ Cache MISS (best similarity: {best_similarity:.3f} < {self.similarity_threshold}, "
                           f"query: '{query[:50]}...')")
            else:
                logger.info(f"✗ Cache MISS (no entries, query: '{query[:50]}...')")

            return None

    def set(self, query: str, result: str):
        """
        Cache query result

        Args:
            query: SQL query
            result: Query result to cache
        """
        if not query or not query.strip():
            return

        # Generate embedding for query
        query_embedding = self.embeddings.generate_embedding(query)

        # Create cache entry
        cache_key = f"query_{len(self._cache)}"
        entry = CacheEntry(
            query=query,
            result=result,
            embedding=query_embedding,
            timestamp=time.time(),
            hit_count=0
        )

        # Add to cache
        self._cache[cache_key] = entry

        logger.info(f"✓ Cached query result (query: '{query[:50]}...', "
                   f"cache_size: {len(self._cache)})")

        # Enforce max entries (LRU eviction)
        if len(self._cache) > self.max_entries:
            self._evict_lru()

    def _evict_lru(self):
        """Evict least recently used entries"""
        # Sort by timestamp (oldest first)
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].timestamp
        )

        # Remove oldest 10% of entries
        num_to_evict = max(1, int(self.max_entries * 0.1))
        for i in range(num_to_evict):
            if i < len(sorted_entries):
                cache_key = sorted_entries[i][0]
                del self._cache[cache_key]
                self._evictions += 1

        logger.info(f"Evicted {num_to_evict} cache entries (total evictions: {self._evictions})")

    def clear_expired(self):
        """Remove expired cache entries"""
        current_time = time.time()
        expired_keys = []

        for cache_key, entry in self._cache.items():
            if current_time - entry.timestamp > self.ttl:
                expired_keys.append(cache_key)

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired cache entries")

    def clear(self):
        """Clear all cache entries"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache metrics
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        # Calculate average hit count
        if self._cache:
            avg_hit_count = sum(e.hit_count for e in self._cache.values()) / len(self._cache)
        else:
            avg_hit_count = 0.0

        return {
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
            "cache_size": len(self._cache),
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl,
            "similarity_threshold": self.similarity_threshold,
            "evictions": self._evictions,
            "avg_hit_count": avg_hit_count
        }

    def get_cached_queries(self) -> List[Tuple[str, int, float]]:
        """
        Get list of cached queries with metadata

        Returns:
            List of (query, hit_count, age_seconds)
        """
        current_time = time.time()
        queries = []

        for entry in self._cache.values():
            age_seconds = current_time - entry.timestamp
            queries.append((entry.query, entry.hit_count, age_seconds))

        # Sort by hit count (descending)
        queries.sort(key=lambda x: x[1], reverse=True)

        return queries


# Global singleton instance
_sql_cache: Optional[SmartSQLCache] = None


def get_sql_cache() -> Optional[SmartSQLCache]:
    """Get global SQL cache instance (may be None if not initialized)"""
    return _sql_cache


def initialize_sql_cache(
    embedding_service: EmbeddingService,
    ttl_seconds: int = 3600,
    similarity_threshold: float = 0.90,
    max_entries: int = 1000
) -> SmartSQLCache:
    """
    Initialize global SQL cache

    Args:
        embedding_service: Embedding service instance
        ttl_seconds: Time-to-live for cache entries
        similarity_threshold: Minimum similarity for cache hit
        max_entries: Maximum cache entries

    Returns:
        Initialized SmartSQLCache instance
    """
    global _sql_cache
    _sql_cache = SmartSQLCache(
        embedding_service=embedding_service,
        ttl_seconds=ttl_seconds,
        similarity_threshold=similarity_threshold,
        max_entries=max_entries
    )
    return _sql_cache
