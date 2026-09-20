"""
Unit and integration tests for SpecVectorStore (ChromaDB persistence and retrieval).
"""

from testpilot.rag.parser import SpecChunk
from testpilot.rag.vector_store import SpecVectorStore


def test_vector_store_initialization():
    store = SpecVectorStore()
    assert store.collection.name == "spec_store"
    assert store.persist_directory == ".chroma_db"
    assert store.count() > 0


def test_index_chunks_and_deduplication():
    store = SpecVectorStore()

    # Create dummy chunks with known IDs
    dummy_chunks = [
        SpecChunk(
            id="test_chunk_id_001",
            content="SPEC TEST RULE: Orders above $100 receive express expedited shipping at zero cost.",
            metadata={"source": "test", "type": "rule", "symbol": "ShippingRule"},
        ),
        SpecChunk(
            id="test_chunk_id_002",
            content="SPEC TEST RULE: Tax computation requires precision rounding to nearest cent.",
            metadata={"source": "test", "type": "rule", "symbol": "TaxRule"},
        ),
    ]

    indexed_count = store.index_chunks(dummy_chunks)
    assert indexed_count == 2

    count_after_first = store.count()

    # Index again with identical IDs - must deduplicate and not inflate count
    reindexed = store.index_chunks(dummy_chunks)
    assert reindexed == 2
    assert store.count() == count_after_first


def test_retrieve_relevant_specs():
    store = SpecVectorStore()
    results = store.retrieve_relevant_specs(query="shipping charges and free threshold", n_results=3)
    assert len(results) <= 3
    assert len(results) > 0

    first = results[0]
    assert "content" in first
    assert "metadata" in first
    assert "distance" in first
    assert isinstance(first["distance"], float)
