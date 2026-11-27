"""Retrieval-Augmented Generation (RAG) document ingestion and semantic synthesis."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.ai.router import MultiModelAIRouter
from backend.app.ai.vector_store import UnifiedVectorStore, VectorRecord
from backend.app.domain.entities import new_id


@dataclass(slots=True)
class RAGIngestResult:
    document_id: str
    chunk_count: int
    backend: str


class RAGPipeline:
    """Chunks documents, stores semantic vectors, and synthesizes grounded answers."""

    def __init__(self, vector_store: UnifiedVectorStore, ai_router: MultiModelAIRouter) -> None:
        self._vectors = vector_store
        self._router = ai_router

    @staticmethod
    def chunk_text(text: str, *, chunk_size: int = 450, overlap: int = 80) -> list[str]:
        cleaned = " ".join(text.split())
        if not cleaned:
            return []
        if len(cleaned) <= chunk_size:
            return [cleaned]
        chunks: list[str] = []
        step = max(50, chunk_size - overlap)
        for start in range(0, len(cleaned), step):
            segment = cleaned[start : start + chunk_size].strip()
            if segment:
                chunks.append(segment)
            if start + chunk_size >= len(cleaned):
                break
        return chunks

    def ingest_document(
        self,
        *,
        user_id: str,
        title: str,
        content: str,
        source: str = "knowledge",
        document_id: str | None = None,
    ) -> RAGIngestResult:
        doc_id = document_id or new_id()
        chunks = self.chunk_text(content)
        for idx, chunk in enumerate(chunks):
            self._vectors.upsert(
                record_id=f"{doc_id}:chunk:{idx}",
                user_id=user_id,
                text=f"{title}: {chunk}",
                metadata={"kind": "rag_chunk", "document_id": doc_id, "title": title, "source": source, "chunk": idx},
            )
        return RAGIngestResult(
            document_id=doc_id,
            chunk_count=len(chunks),
            backend=self._vectors.active_backend,
        )

    def retrieve(self, *, user_id: str, query: str, top_k: int = 5) -> list[VectorRecord]:
        return self._vectors.search(user_id=user_id, query=query, limit=top_k)

    async def query_grounded(self, *, user_id: str, question: str, top_k: int = 4) -> dict:
        contexts = self.retrieve(user_id=user_id, query=question, top_k=top_k)
        context_block = "\n".join(
            f"- [{hit.metadata.get('title', 'note')}] (score={hit.score:.2f}): {hit.text}"
            for hit in contexts
        )
        prompt = (
            f"Question: {question}\n\n"
            f"Retrieved Context:\n{context_block or 'No prior indexed documents found.'}"
        )
        reply = await self._router.generate(
            prompt=prompt,
            system_instruction="Answer concisely using the retrieved context when relevant.",
            task_type="research",
        )
        return {
            "answer": reply.text,
            "provider": reply.provider,
            "model": reply.model,
            "vector_backend": self._vectors.active_backend,
            "citations": [
                {
                    "id": h.id,
                    "title": h.metadata.get("title", h.metadata.get("layer", "memory")),
                    "score": round(h.score, 4),
                    "snippet": h.text[:220],
                }
                for h in contexts
            ],
        }
