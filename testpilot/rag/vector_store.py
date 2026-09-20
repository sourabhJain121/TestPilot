"""
ChromaDB Vector Store Engine for TestPilot AI.
Persists and indexes semantic specification chunks from OpenAPI and Markdown docs.
Uses local SentenceTransformer embeddings with deduplication and similarity search.
"""

import warnings
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from testpilot.rag.parser import SpecChunk, SpecParser

# Suppress non-blocking deprecation warnings from third-party ChromaDB/OpenTelemetry libraries
warnings.filterwarnings("ignore", category=DeprecationWarning)


class LocalSentenceTransformerEmbeddingFunction(EmbeddingFunction):
    """Custom ChromaDB embedding function wrapping sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self._has_model = True
        except Exception:
            self._has_model = False
            self.model = None

    def name(self) -> str:
        """Return the unique name identifier required by ChromaDB EmbeddingFunction."""
        return "sentence-transformers/all-MiniLM-L6-v2"

    def __call__(self, input: Documents) -> Embeddings:
        if self._has_model and self.model:
            embeddings = self.model.encode(list(input), convert_to_numpy=True)
            return embeddings.tolist()

        # Fallback heuristic: simple character-frequency vector if model cannot load
        results = []
        for text in input:
            vec = [0.0] * 384
            for i, ch in enumerate(text[:384]):
                vec[i] = float(ord(ch) % 50) / 50.0
            results.append(vec)
        return results


class SpecVectorStore:
    """
    Manages persistent ChromaDB storage and semantic vector retrieval
    for formal technical specifications.
    """

    COLLECTION_NAME = "spec_store"

    def __init__(self, db_path: str = ".chroma_db"):
        self.db_path = Path(db_path)
        self.persist_directory = str(self.db_path)
        self.collection_name = self.COLLECTION_NAME
        self.db_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(self.db_path))
        self.embedding_fn = LocalSentenceTransformerEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"description": "TestPilot AI Spec-as-Oracle Knowledge Store"},
        )

    def count(self) -> int:
        """Return total number of chunks indexed in the collection."""
        return self.collection.count()

    def index_chunks(self, chunks: list[SpecChunk]) -> int:
        """
        Upsert specification chunks into ChromaDB with deduplication.
        Returns count of indexed documents.
        """
        if not chunks:
            return 0

        ids = [c.id for c in chunks]
        documents = [c.content for c in chunks]
        # Flatten metadata values to string/int/float/bool for ChromaDB compatibility
        metadatas = []
        for c in chunks:
            clean_meta = {}
            for k, v in c.metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)
            metadatas.append(clean_meta)

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        return len(chunks)

    def index_all(
        self,
        openapi_path: str = "testbed/openapi.json",
        docs_dir: str = "docs",
        readme_path: Optional[str] = "README.md",
        spec_path: Optional[str] = None,
    ) -> int:
        """Parse all specifications and upsert them into ChromaDB."""
        target_openapi = spec_path or openapi_path
        chunks = SpecParser.parse_all(openapi_path=target_openapi, docs_dir=docs_dir)
        if readme_path and Path(readme_path).exists() and not any(c.metadata.get("file") == readme_path for c in chunks):
            chunks.extend(SpecParser.parse_markdown(readme_path))
        return self.index_chunks(chunks)

    def retrieve_relevant_specs(
        self,
        query: str,
        n_results: int = 3,
        filter_metadata: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Semantic similarity search across indexed specification chunks.
        Returns structured list of matching documents and metadata.
        """
        if self.count() == 0:
            # Auto-index if vector store is empty
            self.index_all()

        total = self.count()
        actual_n = min(n_results, total)
        if actual_n <= 0:
            return []

        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": actual_n,
        }
        if filter_metadata:
            kwargs["where"] = filter_metadata

        results = self.collection.query(**kwargs)

        extracted = []
        doc_list = results.get("documents", [[]])[0]
        meta_list = results.get("metadatas", [[]])[0]
        dist_list = results.get("distances", [[]])[0] if "distances" in results else [0.0] * len(doc_list)
        id_list = results.get("ids", [[]])[0]

        for doc_id, doc, meta, dist in zip(id_list, doc_list, meta_list, dist_list, strict=False):
            extracted.append(
                {
                    "id": doc_id,
                    "content": doc,
                    "metadata": meta,
                    "distance": dist,
                }
            )

        return extracted
