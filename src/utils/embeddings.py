"""
Azure OpenAI Embeddings Service for RAG and Smart Caching

Provides embedding generation and similarity calculation for:
- RAG document search
- Smart SQL query caching (semantic similarity)

Features:
- In-memory caching of embeddings
- Cosine similarity calculation
- Batch embedding generation
- Production-ready error handling
"""

import hashlib
import logging
from typing import List, Optional, Dict, Any
import numpy as np
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Azure OpenAI Embeddings Service

    Generates embeddings for text using Azure OpenAI API.
    Includes caching to avoid redundant API calls.
    """

    def __init__(
        self,
        azure_endpoint: str,
        api_key: str,
        api_version: str,
        deployment_name: str,
        cache_enabled: bool = True
    ):
        """
        Initialize embeddings service

        Args:
            azure_endpoint: Azure OpenAI endpoint URL
            api_key: Azure OpenAI API key
            api_version: API version (e.g., "2024-08-01-preview")
            deployment_name: Embedding model deployment name
            cache_enabled: Enable in-memory caching
        """
        self.client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version=api_version
        )
        self.deployment_name = deployment_name
        self.cache_enabled = cache_enabled
        self._embedding_cache: Dict[str, List[float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        logger.info(f"✓ Embeddings service initialized (deployment: {deployment_name})")

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text"""
        return hashlib.md5(text.encode()).hexdigest()

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for single text

        Args:
            text: Input text to embed

        Returns:
            1536-dimensional embedding vector

        Raises:
            Exception: If API call fails
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * 1536  # Return zero vector

        # Check cache
        if self.cache_enabled:
            cache_key = self._get_cache_key(text)
            if cache_key in self._embedding_cache:
                self._cache_hits += 1
                logger.debug(f"Cache hit for embedding (total hits: {self._cache_hits})")
                return self._embedding_cache[cache_key]

        # Generate embedding
        try:
            response = self.client.embeddings.create(
                model=self.deployment_name,
                input=[text]
            )

            embedding = response.data[0].embedding

            # Cache result
            if self.cache_enabled:
                cache_key = self._get_cache_key(text)
                self._embedding_cache[cache_key] = embedding
                self._cache_misses += 1
                logger.debug(f"Cache miss - generated new embedding (total misses: {self._cache_misses})")

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}", exc_info=True)
            raise

    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 16) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batched for efficiency)

        Args:
            texts: List of input texts
            batch_size: Number of texts per API call

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        embeddings = []

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Check cache for each text
            batch_embeddings = []
            texts_to_generate = []
            indices_to_generate = []

            for j, text in enumerate(batch):
                if not text or not text.strip():
                    batch_embeddings.append([0.0] * 1536)
                    continue

                cache_key = self._get_cache_key(text)
                if self.cache_enabled and cache_key in self._embedding_cache:
                    batch_embeddings.append(self._embedding_cache[cache_key])
                    self._cache_hits += 1
                else:
                    texts_to_generate.append(text)
                    indices_to_generate.append(j)
                    batch_embeddings.append(None)  # Placeholder

            # Generate missing embeddings
            if texts_to_generate:
                try:
                    response = self.client.embeddings.create(
                        model=self.deployment_name,
                        input=texts_to_generate
                    )

                    for idx, embedding_data in enumerate(response.data):
                        embedding = embedding_data.embedding
                        original_idx = indices_to_generate[idx]
                        batch_embeddings[original_idx] = embedding

                        # Cache result
                        if self.cache_enabled:
                            cache_key = self._get_cache_key(texts_to_generate[idx])
                            self._embedding_cache[cache_key] = embedding
                            self._cache_misses += 1

                except Exception as e:
                    logger.error(f"Batch embedding failed: {e}", exc_info=True)
                    # Fill missing with zero vectors
                    for idx in indices_to_generate:
                        if batch_embeddings[idx] is None:
                            batch_embeddings[idx] = [0.0] * 1536

            embeddings.extend(batch_embeddings)

        logger.info(f"Generated {len(embeddings)} embeddings "
                   f"(cache hits: {self._cache_hits}, misses: {self._cache_misses})")

        return embeddings

    @staticmethod
    def cosine_similarity(emb1: List[float], emb2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings

        Args:
            emb1: First embedding vector
            emb2: Second embedding vector

        Returns:
            Similarity score between 0 and 1
        """
        if not emb1 or not emb2:
            return 0.0

        # Convert to numpy arrays
        vec1 = np.array(emb1)
        vec2 = np.array(emb2)

        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # Clamp to [0, 1]
        return max(0.0, min(1.0, float(similarity)))

    def clear_cache(self):
        """Clear embedding cache"""
        self._embedding_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Embedding cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache hits, misses, size
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_size": len(self._embedding_cache),
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }


# Global singleton instance (initialized in agent_simple.py)
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get global embedding service instance"""
    if _embedding_service is None:
        raise RuntimeError("Embedding service not initialized. Call initialize_embedding_service() first.")
    return _embedding_service


def initialize_embedding_service(
    azure_endpoint: str,
    api_key: str,
    api_version: str,
    deployment_name: str,
    cache_enabled: bool = True
) -> EmbeddingService:
    """
    Initialize global embedding service

    Args:
        azure_endpoint: Azure OpenAI endpoint URL
        api_key: Azure OpenAI API key
        api_version: API version
        deployment_name: Embedding model deployment name
        cache_enabled: Enable caching

    Returns:
        Initialized EmbeddingService instance
    """
    global _embedding_service
    _embedding_service = EmbeddingService(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version,
        deployment_name=deployment_name,
        cache_enabled=cache_enabled
    )
    return _embedding_service
