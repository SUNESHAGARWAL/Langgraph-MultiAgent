"""
Basic tests for Multi-Agent Orchestrator System.
Run with: pytest tests/test_basic.py
"""

import pytest
from src.core.config import config
from src.utils.embeddings import get_embedding_service
from src.services.vector_store import get_vector_store
from src.services.caching import get_smart_cache


class TestConfiguration:
    """Test configuration loading"""

    def test_config_loads(self):
        """Test that config is loaded"""
        assert config is not None
        assert config.app.name == "MultiAgentOrchestrator"
        assert config.app.version == "1.0.0"

    def test_azure_openai_config(self):
        """Test Azure OpenAI configuration"""
        assert config.azure_openai.temperature >= 0
        assert config.azure_openai.max_tokens > 0


class TestEmbeddingService:
    """Test embedding service"""

    def test_embedding_service_init(self):
        """Test embedding service initialization"""
        service = get_embedding_service()
        assert service is not None

    def test_generate_embedding(self):
        """Test embedding generation"""
        service = get_embedding_service()
        text = "Hello world"

        embedding = service.generate_embedding(text)

        assert isinstance(embedding, list)
        assert len(embedding) == config.vector_store.dimension
        assert all(isinstance(x, float) for x in embedding)

    def test_generate_embeddings_batch(self):
        """Test batch embedding generation"""
        service = get_embedding_service()
        texts = ["Hello", "World", "Test"]

        embeddings = service.generate_embeddings_batch(texts)

        assert len(embeddings) == 3
        assert all(len(emb) == config.vector_store.dimension for emb in embeddings)


class TestVectorStore:
    """Test vector store functionality"""

    def test_vector_store_init(self):
        """Test vector store initialization"""
        store = get_vector_store("test_store")
        assert store is not None
        assert store.store_name == "test_store"

    def test_add_and_search(self):
        """Test adding documents and searching"""
        store = get_vector_store("test_search")

        # Add documents
        texts = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a great programming language",
            "Machine learning is fascinating",
        ]

        ids = store.add_documents(texts)
        assert len(ids) == 3

        # Search
        results = store.similarity_search("programming language", k=1)
        assert len(results) > 0

        doc, similarity = results[0]
        assert "Python" in doc["text"]

    def test_get_by_id(self):
        """Test retrieving document by ID"""
        store = get_vector_store("test_getbyid")

        # Add document
        ids = store.add_documents(
            texts=["Test document"],
            ids=["test_id_123"],
        )

        # Retrieve
        doc = store.get_by_id("test_id_123")
        assert doc is not None
        assert doc["id"] == "test_id_123"
        assert doc["text"] == "Test document"


class TestSmartCache:
    """Test smart caching"""

    def test_cache_init(self):
        """Test cache initialization"""
        cache = get_smart_cache()
        assert cache is not None

    def test_cache_set_and_get(self):
        """Test cache set and get"""
        cache = get_smart_cache()

        # Set value
        cache.set("test_key", {"data": "test_value"}, ttl=3600)

        # Get value
        value = cache.get("test_key")
        assert value is not None
        assert value["data"] == "test_value"

    def test_cache_similarity_search(self):
        """Test semantic similarity search"""
        cache = get_smart_cache()

        # Set multiple values
        cache.set(
            "What is Python?",
            {"answer": "Python is a programming language"},
            tags=["test"],
        )

        cache.set(
            "Explain JavaScript",
            {"answer": "JavaScript is a scripting language"},
            tags=["test"],
        )

        # Search for similar query
        results = cache.search_similar(
            "Tell me about Python",
            similarity_threshold=0.7,
            top_k=1,
            tags=["test"],
        )

        # Should find the Python-related cache entry
        assert len(results) > 0
        key, value, similarity = results[0]
        assert "Python" in key


class TestUtilities:
    """Test utility functions"""

    def test_document_parser_exists(self):
        """Test document parser import"""
        from src.utils.parsers import get_document_parser

        parser = get_document_parser()
        assert parser is not None

    def test_logging_setup(self):
        """Test logging setup"""
        from src.utils.logging import get_logger

        logger = get_logger(__name__)
        assert logger is not None

        # Test logging methods exist
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
