"""
Embedding utilities for Azure OpenAI text-embedding-ada-002.
"""

from typing import List
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from src.core.config import config
from src.utils.logging import get_logger, trace_function

logger = get_logger(__name__)


class EmbeddingService:
    """
    Service for generating embeddings using Azure OpenAI.
    Implements caching and batching for efficiency.
    """

    def __init__(self):
        self.client = self._initialize_client()
        self.deployment = config.azure_openai.embedding_deployment
        self._embedding_cache = {}

    def _initialize_client(self) -> AzureOpenAI:
        """Initialize Azure OpenAI client"""
        try:
            # Try with API key first
            if config.azure_openai.api_key:
                client = AzureOpenAI(
                    azure_endpoint=config.azure_openai.endpoint,
                    api_key=config.azure_openai.api_key,
                    api_version=config.azure_openai.api_version,
                )
                logger.info("Initialized Azure OpenAI client with API key")
                return client
        except Exception as e:
            logger.warning(f"Failed to initialize with API key: {e}")

        # Fallback to managed identity
        try:
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default"
            )
            client = AzureOpenAI(
                azure_endpoint=config.azure_openai.endpoint,
                azure_ad_token_provider=token_provider,
                api_version=config.azure_openai.api_version,
            )
            logger.info("Initialized Azure OpenAI client with managed identity")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            raise

    @trace_function("generate_embedding")
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        # Check cache
        if text in self._embedding_cache:
            logger.debug("Returning cached embedding")
            return self._embedding_cache[text]

        try:
            response = self.client.embeddings.create(
                model=self.deployment,
                input=text
            )
            embedding = response.data[0].embedding

            # Cache the result
            self._embedding_cache[text] = embedding

            logger.debug(f"Generated embedding of dimension {len(embedding)}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    @trace_function("generate_embeddings_batch")
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Check which texts are already cached
        uncached_texts = [t for t in texts if t not in self._embedding_cache]

        if uncached_texts:
            try:
                response = self.client.embeddings.create(
                    model=self.deployment,
                    input=uncached_texts
                )

                # Cache new embeddings
                for text, data in zip(uncached_texts, response.data):
                    self._embedding_cache[text] = data.embedding

                logger.info(
                    f"Generated {len(uncached_texts)} embeddings, "
                    f"{len(texts) - len(uncached_texts)} from cache"
                )

            except Exception as e:
                logger.error(f"Failed to generate batch embeddings: {e}")
                raise

        # Return embeddings in original order
        return [self._embedding_cache[t] for t in texts]

    def clear_cache(self):
        """Clear the embedding cache"""
        self._embedding_cache.clear()
        logger.info("Cleared embedding cache")


# Global embedding service instance
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Get global embedding service instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
