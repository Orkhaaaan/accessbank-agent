"""RAG service with ChromaDB and OpenAI embeddings."""

import hashlib
import json
import os
from pathlib import Path
from typing import List, Optional, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI

from config import get_settings
from utils.logging_utils import log_event
from utils.token_tracker import token_tracker

settings = get_settings()
MAX_CHUNK_TOKENS = 300  # approx chars / 4

_rag_instance: Optional["RAGService"] = None


class RAGService:
    def __init__(self) -> None:
        self.persist_dir = Path(settings.chroma_persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="accessbank_kb",
            metadata={"hnsw:space": "cosine"},
        )
        self._openai: Optional[OpenAI] = None
        if settings.openai_api_key:
            self._openai = OpenAI(api_key=settings.openai_api_key)

    def _chunk_text(self, text: str, doc_id: str) -> List[dict]:
        """Split into chunks max ~300 tokens (~1200 chars)."""
        max_chars = MAX_CHUNK_TOKENS * 4
        if len(text) <= max_chars:
            return [{"id": doc_id, "text": text}]
        chunks = []
        words = text.split()
        current = []
        idx = 0
        for w in words:
            current.append(w)
            if len(" ".join(current)) > max_chars:
                chunk_id = f"{doc_id}_{idx}"
                chunks.append({"id": chunk_id, "text": " ".join(current)})
                current = []
                idx += 1
        if current:
            chunks.append({"id": f"{doc_id}_{idx}", "text": " ".join(current)})
        return chunks

    def _embed(self, texts: List[str]) -> List[List[float]]:
        if not self._openai:
            # Deterministic pseudo-embedding for offline demo (384-dim)
            dim = 384
            result = []
            for t in texts:
                h = hashlib.sha256(t.encode()).digest()
                result.append([((h[i % len(h)] + i) % 256) / 255.0 for i in range(dim)])
            return result
        response = self._openai.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        total_tokens = response.usage.total_tokens if response.usage else 0
        token_tracker.record("text-embedding-3-small", total_tokens, 0)
        return [d.embedding for d in response.data]

    def _existing_ids(self) -> set:
        try:
            result = self.collection.get()
            return set(result.get("ids", []) or [])
        except Exception:
            return set()

    def ingest_knowledge_base(self, kb_path: Optional[str] = None) -> int:
        """Ingest JSON knowledge base; skip existing chunk IDs (cache)."""
        if kb_path is None:
            kb_path = str(
                Path(__file__).parent.parent / "data" / "knowledge_base.json"
            )
        with open(kb_path, encoding="utf-8") as f:
            documents = json.load(f)

        existing = self._existing_ids()
        all_chunks = []
        for doc in documents:
            doc_id = doc.get("id", hashlib.md5(doc["text"].encode()).hexdigest()[:8])
            for chunk in self._chunk_text(doc["text"], doc_id):
                if chunk["id"] not in existing:
                    all_chunks.append(
                        {
                            "id": chunk["id"],
                            "text": chunk["text"],
                            "metadata": {"topic": doc.get("topic", ""), "doc_id": doc_id},
                        }
                    )

        if not all_chunks:
            log_event("rag_ingest", status="cached", new_chunks=0)
            return 0

        texts = [c["text"] for c in all_chunks]
        embeddings = self._embed(texts)
        self.collection.add(
            ids=[c["id"] for c in all_chunks],
            documents=texts,
            embeddings=embeddings,
            metadatas=[c["metadata"] for c in all_chunks],
        )
        log_event("rag_ingest", new_chunks=len(all_chunks))
        return len(all_chunks)

    def retrieve(self, query: str, top_k: int = 3) -> Tuple[List[str], int]:
        """Return top_k relevant chunks only (max 3, hackathon rule)."""
        top_k = min(3, top_k)
        if self.collection.count() == 0:
            self.ingest_knowledge_base()

        if not query.strip():
            return [], 0

        query_embedding = self._embed([query])[0]
        # Keyword boost for common FAQ topics (improves offline + online retrieval)
        query_lower = query.lower()
        topic_filter = None
        if any(w in query_lower for w in ["iş saat", "working hour", "saat", "açıq", "bağlı"]):
            topic_filter = "working_hours"
        elif any(w in query_lower for w in ["əlaqə", "contact", "151", "whatsapp"]):
            topic_filter = "contact"

        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(10, max(top_k, self.collection.count())),
            "include": ["documents", "metadatas", "distances"],
        }
        if topic_filter:
            query_kwargs["where"] = {"topic": topic_filter}

        try:
            results = self.collection.query(**query_kwargs)
        except Exception:
            query_kwargs.pop("where", None)
            results = self.collection.query(**query_kwargs)

        docs = results.get("documents", [[]])[0] or []
        # Trim each chunk to ~300 tokens
        trimmed = []
        tokens_used = 0
        for d in docs:
            chunk = d[: MAX_CHUNK_TOKENS * 4]
            trimmed.append(chunk)
            tokens_used += len(chunk) // 4
        return trimmed, tokens_used


def get_rag_service() -> RAGService:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGService()
    return _rag_instance
