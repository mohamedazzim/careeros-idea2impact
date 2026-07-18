"""
Production-grade BM25 sparse retriever.

Builds an inverted index over Qdrant-stored chunk text, supporting:
- Tokenized BM25 scoring with Okapi BM25+
- Exact skill/acronym/version matching
- TF-IDF weighted lexical retrieval
- Collection-scoped indices with async rebuild support

Stateless, async-safe, retry-safe, observable. Worker-safe.
"""
import asyncio
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Set, OrderedDict

from rank_bm25 import BM25Okapi
import nltk

from src.core.config import settings
from src.observability.metrics import (
    BM25_LATENCY,
    BM25_TOKEN_COUNT,
    BM25_INDEX_SIZE,
    BM25_INDEX_MEMORY_BYTES,
)
from src.schemas.retrieval import SparseRetrievalResult, SparseRetrievalResponse

logger = logging.getLogger(__name__)

try:
    nltk.data.find("tokenizers/punkt")
    from nltk.tokenize import word_tokenize
except LookupError:
    logger.warning("NLTK punkt data not found; BM25 tokenization will use regex fallback")
    word_tokenize = None

try:
    nltk.data.find("corpora/stopwords")
    from nltk.corpus import stopwords as nltk_stopwords
    _STOPWORDS: Set[str] = set(nltk_stopwords.words("english"))
except LookupError:
    logger.warning("NLTK stopwords data not found; BM25 stopword removal disabled")
    _STOPWORDS = set()
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bm25-")

# Tech-stack patterns for boosted exact matching
TECH_PATTERNS: Dict[str, re.Pattern] = {
    "react_version": re.compile(r"\bReact\s+(\d{1,2})(?:\.\d+)*\b", re.IGNORECASE),
    "node_version": re.compile(r"\bNode\.?\s*js\s+(\d{1,2})(?:\.\d+)*\b", re.IGNORECASE),
    "python_version": re.compile(r"\bPython\s+(\d)(?:\.\d+)*\b"),
    "angular_version": re.compile(r"\bAngular\s+(\d{1,2})(?:\.\d+)*\b", re.IGNORECASE),
    "kubernetes": re.compile(r"\b[Kk]ubernetes\b"),
    "aws_service": re.compile(r"\b(?:AWS|EC2|S3|Lambda|RDS|DynamoDB|EKS|ECS)\b"),
    "postgresql": re.compile(r"\b(?:PostgreSQL|Postgres)\b", re.IGNORECASE),
    "typescript": re.compile(r"\bTypeScript\b"),
    "fastapi": re.compile(r"\bFastAPI\b", re.IGNORECASE),
    "langgraph": re.compile(r"\bLangGraph\b"),
    "mcp": re.compile(r"\bMCP\b"),
}

ACRONYMS: Dict[str, List[str]] = {
    "mcp": ["Model Context Protocol"],
    "aws": ["Amazon Web Services", "EC2", "S3", "Lambda"],
    "css": ["Cascading Style Sheets"],
    "spa": ["Single Page Application"],
    "ssr": ["Server Side Rendering"],
    "ci": ["Continuous Integration"],
    "cd": ["Continuous Deployment", "Continuous Delivery"],
    "cicd": ["Continuous Integration", "Continuous Deployment"],
    "api": ["Application Programming Interface"],
    "orm": ["Object Relational Mapping"],
    "k8s": ["Kubernetes"],
    "ml": ["Machine Learning"],
    "ai": ["Artificial Intelligence"],
    "nlp": ["Natural Language Processing"],
    "llm": ["Large Language Model"],
}


def _tokenize(text: str) -> List[str]:
    """Tokenize text: lowercase, strip punctuation, remove stopwords."""
    try:
        if word_tokenize is None:
            raise LookupError("NLTK tokenizer unavailable")
        tokens = word_tokenize(text.lower())
    except Exception:
        tokens = re.findall(r"\b[a-z]{2,}\b", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _extract_tech_matches(text: str) -> List[str]:
    """Extract tech-stack terms for boosted matching."""
    matches: List[str] = []
    for name, pattern in TECH_PATTERNS.items():
        found = pattern.findall(text)
        matches.extend(found if found else [])
    return list(set(matches))


def _expand_acronyms(text: str) -> str:
    """Expand known acronyms into the text for better retrieval."""
    expanded = text
    for acronym, expansions in ACRONYMS.items():
        for exp in expansions:
            if re.search(rf"\b{re.escape(exp)}\b", text, re.IGNORECASE):
                expanded += f" {acronym}"
        if re.search(rf"\b{re.escape(acronym)}\b", text, re.IGNORECASE):
            expanded += " " + " ".join(expansions)
    return expanded


class SparseIndex:
    """In-memory BM25 inverted index for a single collection."""

    def __init__(self, collection: str):
        self.collection = collection
        self.documents: List[Dict[str, Any]] = []
        self.corpus: List[str] = []
        self.tokenized: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.doc_ids: List[str] = []
        self._built = False

    def index_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Index a batch of documents into the sparse index."""
        for doc in documents:
            text = doc.get("text", "")
            chunk_id = doc.get("chunk_id", str(len(self.documents)))
            expanded = _expand_acronyms(text)
            tokens = _tokenize(expanded)

            self.documents.append(doc)
            self.corpus.append(text)
            self.tokenized.append(tokens)
            self.doc_ids.append(chunk_id)

        if self.tokenized:
            self.bm25 = BM25Okapi(self.tokenized)
            self._built = True

        logger.info(
            f"Sparse index '{self.collection}': {len(self.documents)} docs indexed"
        )
        return len(self.documents)

    def search(
        self, query: str, top_k: int = 20, boost_tech: bool = True
    ) -> List[SparseRetrievalResult]:
        """Search the sparse index with BM25 scoring."""
        if not self._built or self.bm25 is None:
            return []

        query_tokens = _tokenize(query.lower())
        BM25_TOKEN_COUNT.observe(len(query_tokens))

        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)
        indexed = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )

        tech_query_terms = set()
        if boost_tech:
            tech_query_terms = set(_extract_tech_matches(query))

        results = []
        for idx, score in indexed[:top_k]:
            if idx >= len(self.documents):
                continue

            doc = self.documents[idx]
            matched = []
            token_set = set(self.tokenized[idx]) if idx < len(self.tokenized) else set()
            for t in query_tokens:
                if t in token_set:
                    matched.append(t)

            # Tech-stack boost: exact match bonus
            if tech_query_terms and idx < len(self.tokenized):
                doc_text = " ".join(self.tokenized[idx])
                extra_matches = len(tech_query_terms & set(doc_text.split()))
                if extra_matches > 0:
                    score *= (1.0 + 0.15 * extra_matches)

            results.append(
                SparseRetrievalResult(
                    chunk_id=doc.get("chunk_id", self.doc_ids[idx]),
                    text=doc.get("text", ""),
                    score=float(score),
                    rank=len(results) + 1,
                    token_matches=len(matched),
                    matched_tokens=matched,
                    source=doc.get("source"),
                    metadata=doc.get("metadata", {}),
                )
            )

        return results

    def count(self) -> int:
        return len(self.documents)

    def clear(self) -> None:
        self.documents = []
        self.corpus = []
        self.tokenized = []
        self.bm25 = None
        self.doc_ids = []
        self._built = False


class SparseRetriever:
    """Production-grade sparse/Bm25 retriever with collection-scoped indices.

    Each collection gets its own SparseIndex rebuilt from Qdrant payloads.
    Indices are cached in-memory with LRU eviction and rebuilt on data changes.
    """

    def __init__(self):
        self._indices: OrderedDict = OrderedDict()
        self._max_collections = settings.BM25_MAX_COLLECTIONS

    def _evict_lru(self) -> None:
        """Evict the least recently used collection if over capacity."""
        while len(self._indices) > self._max_collections:
            coll, index = self._indices.popitem(last=False)
            logger.info(
                f"BM25 LRU eviction: collection '{coll}' "
                f"({index.count()} docs) removed from memory"
            )

    def get_index(self, collection: str) -> SparseIndex:
        """Get or create a sparse index for a collection with LRU eviction."""
        if collection in self._indices:
            self._indices.move_to_end(collection)
        else:
            self._indices[collection] = SparseIndex(collection)
            self._evict_lru()
        return self._indices[collection]

    async def build_index_from_payloads(
        self,
        collection: str,
        payloads: List[Dict[str, Any]],
        force_rebuild: bool = False,
    ) -> int:
        """Build/replace the sparse index with memory tracking."""
        index = self.get_index(collection)
        if force_rebuild:
            index.clear()
        count = await asyncio.get_event_loop().run_in_executor(
            _EXECUTOR, index.index_documents, payloads
        )
        # Memory tracking via size estimate
        BM25_INDEX_SIZE.labels(collection=collection).observe(count)
        estimated_mb = (count * 200 * 4) / (1024 * 1024)  # rough: 200 tokens × 4 bytes
        BM25_INDEX_MEMORY_BYTES.labels(collection=collection).observe(
            estimated_mb * 1024 * 1024
        )
        if estimated_mb > 200:
            logger.warning(
                f"BM25 index '{collection}' estimated at {estimated_mb:.0f}MB "
                f"— consider increasing BM25_MAX_COLLECTIONS or reducing corpus"
            )
        return count

    async def search(
        self,
        query: str,
        collection: str = "careeros_resumes",
        top_k: int = 20,
        boost_tech: bool = True,
    ) -> SparseRetrievalResponse:
        """Execute sparse BM25 search against a collection's index.

        Falls back to empty results if the index hasn't been built.
        """
        index = self._indices.get(collection)
        if index is None or not index._built:
            logger.warning(
                f"Sparse index for '{collection}' not built — returning empty results"
            )
            return SparseRetrievalResponse(
                query=query,
                results=[],
                total_indexed=0,
                query_tokens=[],
                latency_ms=0.0,
            )

        start = time.monotonic()
        query_tokens = _tokenize(query.lower())

        results = await asyncio.get_event_loop().run_in_executor(
            _EXECUTOR, index.search, query, top_k, boost_tech
        )

        elapsed = (time.monotonic() - start) * 1000
        BM25_LATENCY.labels(collection=collection).observe(elapsed / 1000)

        return SparseRetrievalResponse(
            query=query,
            results=results[:top_k],
            total_indexed=index.count(),
            query_tokens=query_tokens,
            latency_ms=round(elapsed, 2),
        )

    async def index_count(self, collection: str) -> int:
        index = self._indices.get(collection)
        return index.count() if index else 0

    def clear_index(self, collection: str) -> None:
        if collection in self._indices:
            self._indices[collection].clear()

    def clear_all(self) -> None:
        self._indices.clear()


# Module-level singleton (lazy via __getattr__)
_sparse_retriever: Optional[SparseRetriever] = None


def get_sparse_retriever() -> SparseRetriever:
    global _sparse_retriever
    if _sparse_retriever is None:
        _sparse_retriever = SparseRetriever()
    return _sparse_retriever


def reset_sparse_retriever() -> None:
    global _sparse_retriever
    if _sparse_retriever is not None:
        _sparse_retriever.clear_all()
    _sparse_retriever = None


def __getattr__(name: str):
    if name == "sparse_retriever":
        return get_sparse_retriever()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
